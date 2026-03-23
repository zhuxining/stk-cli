"""Longport QuoteContext wrapper — unified data source for all markets."""

from decimal import Decimal

from stk.deps import get_longport_ctx
from stk.errors import SourceError
from stk.models.quote import Quote
from stk.utils.price import calc_change, r2
from stk.utils.symbol import to_longport_symbol


def _build_quote(q, lp_symbol: str) -> Quote:
    """Build Quote from longport response, falling back to history if last_done is zero."""
    last = Decimal(str(q.last_done))
    prev_close = Decimal(str(q.prev_close))

    if last == 0:
        return _fallback_quote(lp_symbol, prev_close, q)

    change, change_pct = calc_change(last, prev_close)
    return Quote(
        symbol=lp_symbol,
        name=getattr(q, "name", ""),
        last=r2(last),
        open=r2(Decimal(str(q.open))),
        high=r2(Decimal(str(q.high))),
        low=r2(Decimal(str(q.low))),
        prev_close=r2(prev_close),
        change=change,
        change_pct=change_pct,
        volume=q.volume,
        turnover=r2(Decimal(str(q.turnover))),
        timestamp=str(q.timestamp),
        source="realtime",
    )


def _fallback_quote(lp_symbol: str, prev_close: Decimal, q) -> Quote:
    """Use most recent candlestick close as last price when realtime is unavailable."""
    from stk.services.history import get_history

    candles = get_history(lp_symbol, count=2)
    if not candles:
        raise SourceError(f"No realtime or history data for {lp_symbol}")

    last = candles[-1].close
    change, change_pct = calc_change(last, prev_close) if prev_close else (None, None)
    return Quote(
        symbol=lp_symbol,
        name=getattr(q, "name", ""),
        last=r2(last),
        prev_close=r2(prev_close) if prev_close else None,
        change=change,
        change_pct=change_pct,
        volume=q.volume,
        source="last_close",
    )


def get_realtime_quotes(symbols: list[str]) -> list[Quote]:
    """Fetch real-time quotes for multiple symbols in a single API call."""
    try:
        ctx = get_longport_ctx()
        lp_symbols = [to_longport_symbol(s) for s in symbols]
        resp = ctx.quote(lp_symbols)
        if not resp:
            raise SourceError(f"No quote data returned for {symbols}")
        result = []
        for idx, q in enumerate(resp):
            result.append(_build_quote(q, lp_symbols[idx]))
        return result
    except SourceError:
        raise
    except Exception as e:
        raise SourceError(f"Longport API error: {e}") from e


def get_realtime_quote(symbol: str) -> Quote:
    """Fetch real-time quote for a single symbol."""
    return get_realtime_quotes([symbol])[0]
