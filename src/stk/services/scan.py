"""Watchlist scan service — batch quote + score in one call."""

from loguru import logger

from stk.models.scan import ScanItem, ScanResult
from stk.services.longport_quote import get_realtime_quotes
from stk.services.score import calc_score
from stk.services.watchlist import get_watchlist


def scan_watchlist(name: str, *, sort: str = "change_pct") -> ScanResult:
    """Fetch watchlist members, batch quote, score each, return sorted results."""
    watchlist = get_watchlist(name)
    securities = watchlist.securities
    symbols = [s.symbol for s in securities]
    names_map = {s.symbol: s.name for s in securities}

    # Single API call for all quotes
    quotes = get_realtime_quotes(symbols)
    quote_map = {q.symbol: q for q in quotes}

    items: list[ScanItem] = []
    for symbol in symbols:
        q = quote_map.get(symbol)

        sc = None
        try:
            sc = calc_score(symbol)
        except Exception as e:
            logger.debug(f"Score failed for {symbol}: {e}")

        change_pct = q.change_pct if q else None
        alerts: list[str] = []
        if change_pct is not None:
            cpct = float(change_pct)
            if cpct >= 5:
                alerts.append(f"大涨 ({cpct:+.1f}%)")
            elif cpct <= -3:
                alerts.append(f"大跌 ({cpct:.1f}%)")

        items.append(
            ScanItem(
                symbol=symbol,
                name=names_map.get(symbol, ""),
                last=q.last if q else None,
                change_pct=change_pct,
                source=q.source if q else "unknown",
                score=sc.total_score if sc else None,
                rating=sc.rating if sc else None,
                mode=sc.mode if sc else "stock",
                buy_signals=sc.buy_signals if sc else [],
                sell_signals=sc.sell_signals if sc else [],
                alerts=alerts,
            )
        )

    if sort == "score":
        items.sort(key=lambda x: x.score or 0, reverse=True)
    else:
        items.sort(key=lambda x: float(x.change_pct or 0), reverse=True)

    return ScanResult(group_name=name, total=len(items), items=items)
