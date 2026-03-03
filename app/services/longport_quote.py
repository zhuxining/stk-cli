"""Longport QuoteContext wrapper for HK/US stocks."""

from app.deps import get_longport_ctx
from app.errors import SourceError


def get_realtime_quote(symbol: str) -> dict:
    """Fetch real-time quote from longport."""
    try:
        ctx = get_longport_ctx()
        resp = ctx.quote([symbol])
        if not resp:
            raise SourceError(f"No quote data returned for {symbol}")
        q = resp[0]
        return {
            "symbol": symbol,
            "name": q.symbol,
            "last": q.last_done,
            "open": q.open,
            "high": q.high,
            "low": q.low,
            "prev_close": q.prev_close,
            "volume": q.volume,
            "turnover": q.turnover,
            "timestamp": str(q.timestamp),
        }
    except SourceError:
        raise
    except Exception as e:
        raise SourceError(f"Longport API error: {e}") from e
