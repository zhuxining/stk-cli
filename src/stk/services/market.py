"""Market service — indices, temperature, breadth via longport."""

from decimal import Decimal

from stk.deps import get_longport_ctx
from stk.errors import SourceError
from stk.models.market import IndexQuote, MarketBreadth, MarketTemperature
from stk.utils.price import r2

MAJOR_INDICES = [
    "000001.SH",  # 上证指数
    "399001.SZ",  # 深证成指
    "399006.SZ",  # 创业板指
    "HSI.HK",  # 恒生指数
    ".IXIC",  # 纳斯达克
    ".DJI",  # 道琼斯
    ".SPX",  # 标普500
]


def get_indices() -> list[IndexQuote]:
    """Get major index quotes from longport."""
    try:
        ctx = get_longport_ctx()
        resp = ctx.quote(MAJOR_INDICES)

        results = []
        for q in resp:
            last = r2(Decimal(str(q.last_done)))
            prev = Decimal(str(q.prev_close))
            change = r2(last - prev) if prev else None
            change_pct = r2(change / prev * 100) if (change is not None and prev) else None
            results.append(
                IndexQuote(
                    symbol=q.symbol,
                    name=q.symbol,
                    last=last,
                    change=change,
                    change_pct=change_pct,
                    volume=q.volume,
                )
            )
        return results
    except Exception as e:
        raise SourceError(f"Longport index API error: {e}") from e


def get_temperature() -> MarketTemperature:
    """Get market temperature from longport."""
    try:
        from longport.openapi import Market

        ctx = get_longport_ctx()
        resp = ctx.market_temperature(Market.CN)
        return MarketTemperature(
            score=resp.temperature,
            level=resp.description,
            valuation=resp.valuation,
            sentiment=resp.sentiment,
        )
    except Exception as e:
        raise SourceError(f"Longport temperature API error: {e}") from e


def get_breadth() -> MarketBreadth:
    """Get market breadth. TODO: longport has no advance/decline stats API."""
    raise NotImplementedError("Market breadth not yet implemented (needs akshare)")
