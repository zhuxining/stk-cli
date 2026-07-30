"""Daily monitoring scan service."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from zoneinfo import ZoneInfo

from loguru import logger

from stk.models.quote import Quote
from stk.models.scan import (
    CompactDailyValue,
    FocusItem,
    IgnoredSummary,
    MonitorResult,
    MonitorSummary,
    MonitorUniverse,
    ScanError,
)
from stk.models.score import ContextBias, FactorState, ScoreResult, SignalContext
from stk.services.indicator import get_daily
from stk.services.quote import get_realtime_quotes
from stk.services.score import calc_score
from stk.services.watchlist import get_watchlist
from stk.utils.symbol import to_longport_symbol
from stk.utils.trading_session import is_unclosed_daily_bar

_BIAS_RANK: dict[ContextBias, int] = {
    "supportive": 0,
    "mixed": 1,
    "risky": 2,
    "conflicting": 3,
}
_LOCAL_TZ = ZoneInfo("Asia/Shanghai")
_DAILY10_COUNT = 10
_DEFAULT_FACTOR_STATES: set[FactorState] = {"confirming", "conflicting", "risk", "opportunity"}


def _round_daily_value(value: object, *, digits: int = 4) -> CompactDailyValue:
    if value is None:
        return None
    if isinstance(value, int | str):
        return value
    if isinstance(value, float):
        return round(value, digits)
    return str(value)


def _boll_position_pct(day: dict) -> float | None:
    close = day.get("close")
    upper = day.get("upper")
    lower = day.get("lower")
    if not isinstance(close, int | float):
        return None
    if not isinstance(upper, int | float) or not isinstance(lower, int | float):
        return None
    bandwidth = upper - lower
    if bandwidth <= 0:
        return None
    return round((close - lower) / bandwidth * 100, 1)


def _compact_daily_row(day: dict) -> dict[str, CompactDailyValue]:
    field_map = {
        "date": "date",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume",
        "turnover": "turnover",
        "change_pct": "change_pct",
        "EMA9": "ema9",
        "EMA26": "ema26",
        "Supertrend": "supertrend",
        "SupertrendDirection": "supertrend_direction",
        "MACD": "macd",
        "signal": "macd_signal",
        "hist": "macd_hist",
        "RSI": "rsi14",
        "WR": "wr14",
        "J": "j",
        "ATR10": "atr10",
    }
    row = {
        target: _round_daily_value(day.get(source))
        for source, target in field_map.items()
        if day.get(source) is not None
    }
    if (boll_position := _boll_position_pct(day)) is not None:
        row["boll_position_pct"] = boll_position
    return row


def _get_daily10(symbol: str) -> list[dict[str, CompactDailyValue]]:
    try:
        daily = get_daily(symbol, count=_DAILY10_COUNT + 1)
    except Exception as err:
        logger.debug(f"daily10 supplement failed for {symbol}: {err}")
        return []
    days = daily.days
    if days and is_unclosed_daily_bar(days[0].get("date"), symbol):
        days = days[1:]
    return [_compact_daily_row(day) for day in days[:_DAILY10_COUNT]]


def _run_date() -> str:
    return datetime.now(_LOCAL_TZ).date().isoformat()


def _quote_map(symbols: list[str], names: dict[str, str]) -> dict[str, Quote]:
    try:
        quotes = get_realtime_quotes(symbols)
    except Exception as err:
        logger.debug(f"Batch quote failed: {err}")
        return {}

    quotes_by_symbol = {q.symbol: q for q in quotes}
    for quote in quotes:
        if quote.symbol not in names and quote.name:
            names[quote.symbol] = quote.name
    return quotes_by_symbol


def _score_symbols(
    symbols: list[str],
    *,
    max_workers: int,
) -> tuple[dict[str, ScoreResult], list[ScanError]]:
    score_map: dict[str, ScoreResult] = {}
    errors: list[ScanError] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(calc_score, symbol): symbol for symbol in symbols}
        for future in as_completed(futures):
            symbol = futures[future]
            lp_symbol = to_longport_symbol(symbol)
            try:
                score_map[symbol] = future.result()
            except Exception as err:
                logger.debug(f"Score failed for {symbol}: {err}")
                errors.append(ScanError(symbol=lp_symbol, reason=str(err)))
    return score_map, errors


def _should_focus(score: ScoreResult) -> bool:
    return score.routing.entry_eligible


def _needs_daily10(score: ScoreResult) -> bool:
    return score.routing.entry_eligible or score.routing.recovery


def _compact_context(context: SignalContext) -> SignalContext:
    factors = [factor for factor in context.factors if factor.state in _DEFAULT_FACTOR_STATES]
    return context.model_copy(update={"factors": factors})


def _focus_item(
    symbol: str,
    names: dict[str, str],
    quote_map: dict[str, Quote],
    score: ScoreResult,
    *,
    include_daily10: bool,
    include_full_context: bool,
) -> FocusItem:
    lp_symbol = to_longport_symbol(symbol)
    quote = quote_map.get(lp_symbol)
    return FocusItem(
        symbol=lp_symbol,
        name=names.get(lp_symbol, names.get(symbol, "")),
        decision=score.decision,
        primary_signal=score.primary_signal,
        context=score.context if include_full_context else _compact_context(score.context),
        risk=score.risk,
        routing=score.routing,
        last=quote.last if quote else None,
        change_pct=quote.change_pct if quote else None,
        source=quote.source if quote else "unknown",
        daily10=(_get_daily10(lp_symbol) if include_daily10 and _needs_daily10(score) else None),
    )


def _sort_key(item: FocusItem) -> tuple[int, int, float]:
    state_rank = 0 if item.routing.entry_eligible else 1
    turnover_ratio = item.routing.turnover_ratio_5d or 0
    return (
        state_rank,
        _BIAS_RANK[item.context.overall_bias],
        -turnover_ratio,
    )


def _summary(focus: list[FocusItem], scores: list[ScoreResult]) -> MonitorSummary:
    eligible = sum(score.routing.entry_eligible for score in scores)
    risks = sum(score.routing.exit_trigger for score in scores)
    watches = sum(score.routing.state == "watch" for score in scores)
    return MonitorSummary(
        focus_count=len(focus),
        recommend_count=eligible,
        entry_signal_count=eligible,
        exit_signal_count=risks,
        watch_signal_count=watches,
        risk_count=risks,
    )


def _monitor_symbols(
    symbols: list[str],
    names: dict[str, str],
    *,
    universe_name: str,
    max_workers: int = 8,
    include_daily10: bool = False,
    include_full_context: bool = False,
) -> MonitorResult:
    if not symbols:
        return MonitorResult(
            run_date=_run_date(),
            universe=MonitorUniverse(name=universe_name, total=0, scanned=0, failed=0),
            summary=MonitorSummary(
                focus_count=0,
                recommend_count=0,
                entry_signal_count=0,
                exit_signal_count=0,
                watch_signal_count=0,
            ),
            focus=[],
            risk=[],
            ignored=IgnoredSummary(no_signal_count=0),
            errors=[],
        )

    quotes = _quote_map(symbols, names)
    score_map, errors = _score_symbols(symbols, max_workers=max_workers)

    focus = [
        _focus_item(
            symbol,
            names,
            quotes,
            score,
            include_daily10=include_daily10,
            include_full_context=include_full_context,
        )
        for symbol, score in score_map.items()
        if _should_focus(score)
    ]
    risk = [
        _focus_item(
            symbol,
            names,
            quotes,
            score,
            include_daily10=False,
            include_full_context=include_full_context,
        )
        for symbol, score in score_map.items()
        if score.routing.exit_trigger
    ]
    focus.sort(key=_sort_key)
    risk.sort(key=_sort_key)

    return MonitorResult(
        run_date=_run_date(),
        universe=MonitorUniverse(
            name=universe_name,
            total=len(symbols),
            scanned=len(score_map),
            failed=len(errors),
        ),
        summary=_summary(focus, list(score_map.values())),
        focus=focus,
        risk=risk,
        ignored=IgnoredSummary(no_signal_count=len(score_map) - len(focus) - len(risk)),
        errors=errors,
    )


def scan_watchlist(
    name: str,
    *,
    include_daily10: bool = False,
    include_full_context: bool = False,
) -> MonitorResult:
    """Monitor a watchlist and return symbols that need daily focus."""
    watchlist = get_watchlist(name)
    symbols = [security.symbol for security in watchlist.securities]
    names_map = {security.symbol: security.name for security in watchlist.securities}
    return _monitor_symbols(
        symbols,
        names_map,
        universe_name=name,
        include_daily10=include_daily10,
        include_full_context=include_full_context,
    )
