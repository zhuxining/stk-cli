"""Daily monitoring scan service."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from zoneinfo import ZoneInfo

from loguru import logger

from stk.models.quote import Quote
from stk.models.scan import (
    CompactDailyValue,
    FocusItem,
    FocusPriority,
    IgnoredSummary,
    MonitorResult,
    MonitorSummary,
    MonitorUniverse,
    ScanError,
)
from stk.models.score import ContextBias, ScoreResult, SignalLevel
from stk.services.indicator import get_daily
from stk.services.quote import get_realtime_quotes
from stk.services.score import calc_score
from stk.services.watchlist import get_watchlist
from stk.utils.symbol import to_longport_symbol

_FOCUS_LEVELS: set[SignalLevel] = {"strong_buy", "buy", "sell", "strong_sell"}
_ACTIVE_SIGNAL_STATUSES = {"new", "active"}
_PRIORITY_RANK: dict[FocusPriority, int] = {"high": 0, "medium": 1, "low": 2}
_BIAS_RANK: dict[ContextBias, int] = {
    "supportive": 0,
    "mixed": 1,
    "risky": 2,
    "conflicting": 3,
}
_LOCAL_TZ = ZoneInfo("Asia/Shanghai")
_HIGH_PRIORITY_DAILY_COUNT = 10
_WATCH_CONTEXT_MAX_BARS = 10


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


def _get_high_priority_daily10(symbol: str) -> list[dict[str, CompactDailyValue]]:
    try:
        daily = get_daily(symbol, count=_HIGH_PRIORITY_DAILY_COUNT)
    except Exception as err:
        logger.debug(f"High priority daily supplement failed for {symbol}: {err}")
        return []
    return [_compact_daily_row(day) for day in daily.days]


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


def _has_watch_context(score: ScoreResult) -> bool:
    actionable_factors = sum(
        factor.state in {"risk", "opportunity"} for factor in score.context.factors
    )
    if actionable_factors == 0 and not score.context.warnings:
        return False

    bars = score.decision.bars_since_signal
    if bars is None or bars > _WATCH_CONTEXT_MAX_BARS:
        return score.decision.direction == "neutral" and actionable_factors >= 2

    return (
        bool(score.context.warnings)
        or actionable_factors >= 2
        or score.context.overall_bias in {"risky", "conflicting"}
    )


def _should_focus(score: ScoreResult) -> bool:
    decision = score.decision
    if decision.level in _FOCUS_LEVELS and decision.signal_status in _ACTIVE_SIGNAL_STATUSES:
        return True
    return decision.level == "hold" and _has_watch_context(score)


def _priority(score: ScoreResult) -> FocusPriority:
    level = score.decision.level
    bias = score.context.overall_bias
    if level in {"strong_buy", "strong_sell"} and bias != "conflicting":
        return "high"
    if level in _FOCUS_LEVELS:
        return "medium"
    return "low"


def _focus_item(
    symbol: str,
    names: dict[str, str],
    quote_map: dict[str, Quote],
    score: ScoreResult,
) -> FocusItem:
    lp_symbol = to_longport_symbol(symbol)
    quote = quote_map.get(lp_symbol)
    priority = _priority(score)
    return FocusItem(
        symbol=lp_symbol,
        name=names.get(lp_symbol, names.get(symbol, "")),
        priority=priority,
        decision=score.decision,
        primary_signal=score.primary_signal,
        context=score.context,
        risk=score.risk,
        last=quote.last if quote else None,
        change_pct=quote.change_pct if quote else None,
        source=quote.source if quote else "unknown",
        daily10=_get_high_priority_daily10(lp_symbol) if priority == "high" else None,
    )


def _sort_key(item: FocusItem) -> tuple[int, int, float, int]:
    bars = item.decision.bars_since_signal
    bars_since_signal = 999 if bars is None else bars
    return (
        _PRIORITY_RANK[item.priority],
        _BIAS_RANK[item.context.overall_bias],
        -item.decision.confidence,
        bars_since_signal,
    )


def _summary(focus: list[FocusItem]) -> MonitorSummary:
    return MonitorSummary(
        focus_count=len(focus),
        high_priority_count=sum(item.priority == "high" for item in focus),
        entry_signal_count=sum(item.decision.action == "focus_buy" for item in focus),
        exit_signal_count=sum(item.decision.action == "focus_sell" for item in focus),
        watch_signal_count=sum(item.decision.action == "watch" for item in focus),
    )


def _monitor_symbols(
    symbols: list[str],
    names: dict[str, str],
    *,
    universe_name: str,
    max_workers: int = 8,
) -> MonitorResult:
    if not symbols:
        return MonitorResult(
            run_date=_run_date(),
            universe=MonitorUniverse(name=universe_name, total=0, scanned=0, failed=0),
            summary=MonitorSummary(
                focus_count=0,
                high_priority_count=0,
                entry_signal_count=0,
                exit_signal_count=0,
                watch_signal_count=0,
            ),
            focus=[],
            ignored=IgnoredSummary(no_signal_count=0),
            errors=[],
        )

    quotes = _quote_map(symbols, names)
    score_map, errors = _score_symbols(symbols, max_workers=max_workers)

    focus = [
        _focus_item(symbol, names, quotes, score)
        for symbol, score in score_map.items()
        if _should_focus(score)
    ]
    focus.sort(key=_sort_key)

    return MonitorResult(
        run_date=_run_date(),
        universe=MonitorUniverse(
            name=universe_name,
            total=len(symbols),
            scanned=len(score_map),
            failed=len(errors),
        ),
        summary=_summary(focus),
        focus=focus,
        ignored=IgnoredSummary(no_signal_count=len(score_map) - len(focus)),
        errors=errors,
    )


def scan_watchlist(name: str) -> MonitorResult:
    """Monitor a watchlist and return symbols that need daily focus."""
    watchlist = get_watchlist(name)
    symbols = [security.symbol for security in watchlist.securities]
    names_map = {security.symbol: security.name for security in watchlist.securities}
    return _monitor_symbols(symbols, names_map, universe_name=name)


def batch_summary(symbols: list[str]) -> MonitorResult:
    """Monitor an ad-hoc symbol universe and return symbols that need daily focus."""
    return _monitor_symbols(symbols, {}, universe_name="ad-hoc")


def kline_watchlist(name: str, *, period: str = "day", count: int = 10) -> list:
    """Fetch K-line + all indicators for every stock in a watchlist group."""
    watchlist = get_watchlist(name)
    symbols = [s.symbol for s in watchlist.securities]

    results: list = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(get_daily, s, period=period, count=count): s for s in symbols}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                logger.debug(f"kline failed for {futures[future]}: {e}")
    return results
