"""Historical candlestick data service via longport."""

from decimal import Decimal

import pandas as pd

from stk.deps import get_longport_ctx
from stk.errors import SourceError
from stk.models.common import TargetType
from stk.models.history import Candlestick
from stk.store.cache import cached
from stk.utils.symbol import to_longport_symbol


def candles_to_df(candles: list) -> pd.DataFrame:
    """Convert Candlestick list to DataFrame with float OHLCV columns."""
    df = pd.DataFrame([c.model_dump() for c in candles])
    for col in ("open", "high", "low", "close", "turnover"):
        if col in df.columns:
            df[col] = df[col].astype(float)
    return df


_PERIOD_MAP: dict[str, object] = {}


def _get_period(period: str):
    """Lazy-load longport Period enum and map string to enum value."""
    if not _PERIOD_MAP:
        from longport.openapi import Period

        _PERIOD_MAP.update({
            "day": Period.Day,
            "week": Period.Week,
            "month": Period.Month,
        })
    lp_period = _PERIOD_MAP.get(period)
    if lp_period is None:
        raise SourceError(f"Unsupported period: {period}. Use day/week/month")
    return lp_period


@cached(ttl=3600)
def get_history(
    symbol: str,
    *,
    target_type: TargetType = TargetType.STOCK,
    period: str = "day",
    count: int = 30,
) -> list[Candlestick]:
    """Get historical candlestick data from longport."""
    try:
        from longport.openapi import AdjustType

        ctx = get_longport_ctx()
        lp_symbol = to_longport_symbol(symbol)
        lp_period = _get_period(period)

        resp = ctx.candlesticks(lp_symbol, lp_period, count, AdjustType.ForwardAdjust)
        return [
            Candlestick(
                date=str(c.timestamp),
                open=Decimal(str(c.open)),
                high=Decimal(str(c.high)),
                low=Decimal(str(c.low)),
                close=Decimal(str(c.close)),
                volume=c.volume,
                turnover=Decimal(str(c.turnover)),
            )
            for c in resp
        ]
    except SourceError:
        raise
    except Exception as e:
        raise SourceError(f"Longport history API error: {e}") from e
