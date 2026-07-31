"""Concurrent Longport group signal scanning."""

from concurrent.futures import ThreadPoolExecutor, as_completed

from loguru import logger

from stk.errors import error_code
from stk.models.common import BatchFailure
from stk.models.quote import Quote
from stk.models.scan import (
    QuoteSnapshot,
    ScanResult,
    ScanSummary,
    SignalDetail,
    SignalItem,
)
from stk.models.score import ContextBias, StockAssessment
from stk.services.quote import get_realtime_quotes
from stk.services.score import calc_score
from stk.services.watchlist import get_watchlist
from stk.utils.symbol import to_longport_symbol

_BIAS_RANK: dict[ContextBias, int] = {
    "supportive": 0,
    "mixed": 1,
    "risky": 2,
    "conflicting": 3,
}


def _quote_map(symbols: list[str], names: dict[str, str]) -> dict[str, Quote]:
    try:
        quotes = get_realtime_quotes(symbols)
    except Exception as err:
        logger.debug(f"Batch quote failed: {err}")
        return {}
    for quote in quotes:
        if quote.symbol not in names and quote.name:
            names[quote.symbol] = quote.name
    return {quote.symbol: quote for quote in quotes}


def _assess_symbols(
    symbols: list[str],
    *,
    max_workers: int,
    recent_bars: int,
    include_factors: bool,
) -> tuple[list[StockAssessment], list[BatchFailure]]:
    assessments: list[StockAssessment] = []
    failures: list[BatchFailure] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                calc_score,
                symbol,
                recent_bars=recent_bars,
                include_factors=include_factors,
            ): symbol
            for symbol in symbols
        }
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                assessments.append(future.result())
            except Exception as err:
                logger.debug(f"Assessment failed for {symbol}: {err}")
                failures.append(
                    BatchFailure(
                        symbol=to_longport_symbol(symbol),
                        code=error_code(err),
                        message=str(err),
                    )
                )
    return assessments, failures


def _signal_item(
    assessment: StockAssessment,
    *,
    names: dict[str, str],
    quotes: dict[str, Quote],
) -> SignalItem:
    quote = quotes.get(assessment.symbol)
    return SignalItem(
        symbol=assessment.symbol,
        name=names.get(assessment.symbol, ""),
        as_of=assessment.as_of,
        quote=(
            QuoteSnapshot(
                last=quote.last,
                change_pct=quote.change_pct,
                source=quote.source,
            )
            if quote
            else None
        ),
        signal=SignalDetail(
            triggers=assessment.triggers,
            reasons=assessment.reasons,
        ),
        indicators=assessment.indicators,
        quality=assessment.quality,
        risk=assessment.risk,
        recent_bars=assessment.recent_bars,
    )


def _sort_key(item: SignalItem) -> tuple[int, float]:
    turnover_ratio = item.indicators.turnover_ratio_5d or 0
    return _BIAS_RANK[item.quality.bias], -turnover_ratio


def _failure_key(item: BatchFailure) -> str:
    return item.symbol or ""


def _monitor_symbols(
    symbols: list[str],
    names: dict[str, str],
    *,
    group: str,
    max_workers: int = 8,
    recent_bars: int = 0,
    include_factors: bool = False,
) -> ScanResult:
    quotes = _quote_map(symbols, names) if symbols else {}
    assessments, failures = _assess_symbols(
        symbols,
        max_workers=max_workers,
        recent_bars=recent_bars,
        include_factors=include_factors,
    )
    buy = [
        _signal_item(item, names=names, quotes=quotes)
        for item in assessments
        if item.state == "buy"
    ]
    sell = [
        _signal_item(item, names=names, quotes=quotes)
        for item in assessments
        if item.state == "sell"
    ]
    buy.sort(key=_sort_key)
    sell.sort(key=_sort_key)
    watch_count = sum(item.state == "watch" for item in assessments)
    ignored_count = sum(item.state == "ignored" for item in assessments)
    return ScanResult(
        group=group,
        summary=ScanSummary(
            total=len(symbols),
            analyzed=len(assessments),
            failed=len(failures),
            buy=len(buy),
            sell=len(sell),
            watch=watch_count,
            ignored=ignored_count,
        ),
        buy=buy,
        sell=sell,
        failures=sorted(failures, key=_failure_key),
    )


def scan_watchlist(
    name: str,
    *,
    recent_bars: int = 0,
    include_factors: bool = False,
) -> ScanResult:
    """Scan one Longport group using confirmed daily bars."""
    watchlist = get_watchlist(name)
    symbols = [security.symbol for security in watchlist.securities]
    names = {security.symbol: security.name for security in watchlist.securities}
    return _monitor_symbols(
        symbols,
        names,
        group=name,
        recent_bars=recent_bars,
        include_factors=include_factors,
    )
