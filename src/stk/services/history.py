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
            "1m": Period.Min_1,
            "2m": Period.Min_2,
            "3m": Period.Min_3,
            "5m": Period.Min_5,
            "10m": Period.Min_10,
            "15m": Period.Min_15,
            "20m": Period.Min_20,
            "30m": Period.Min_30,
            "45m": Period.Min_45,
            "60m": Period.Min_60,
            "120m": Period.Min_120,
            "180m": Period.Min_180,
            "240m": Period.Min_240,
        })
    lp_period = _PERIOD_MAP.get(period)
    if lp_period is None:
        raise SourceError(f"Unsupported period: {period}. Use day/week/month or minute periods")
    return lp_period


def _query_history(
    symbol: str,
    *,
    target_type: TargetType = TargetType.STOCK,
    period: str = "day",
    count: int = 30,
) -> list[Candlestick]:
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


@cached(ttl=3600, disk=True)
def get_history(
    symbol: str,
    *,
    target_type: TargetType = TargetType.STOCK,
    period: str = "day",
    count: int = 30,
) -> list[Candlestick]:
    """Get historical candlestick data from longport."""
    return _query_history(symbol, target_type=target_type, period=period, count=count)


def get_uncached_history(
    symbol: str,
    *,
    target_type: TargetType = TargetType.STOCK,
    period: str = "day",
    count: int = 30,
) -> list[Candlestick]:
    """Get fresh candlestick data without the long-lived history cache."""
    return _query_history(symbol, target_type=target_type, period=period, count=count)
