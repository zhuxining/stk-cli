"""Longport QuoteContext wrapper — unified data source for all markets."""

from decimal import Decimal

from stk.deps import get_longport_ctx
from stk.errors import SourceError
from stk.models.quote import Quote
from stk.utils.price import r2
from stk.utils.symbol import to_longport_symbol


def get_realtime_quote(symbol: str) -> Quote:
    """Fetch real-time quote from longport."""
    try:
        ctx = get_longport_ctx()
        lp_symbol = to_longport_symbol(symbol)
        resp = ctx.quote([lp_symbol])
        if not resp:
            raise SourceError(f"No quote data returned for {symbol}")
        q = resp[0]

        last = Decimal(str(q.last_done))
        prev_close = Decimal(str(q.prev_close))
        change = r2(last - prev_close) if prev_close else None
        change_pct = r2(change / prev_close * 100) if (change is not None and prev_close) else None

        return Quote(
            symbol=lp_symbol,
            name=q.symbol,
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
        )
    except SourceError:
        raise
    except Exception as e:
        raise SourceError(f"Longport API error: {e}") from e
