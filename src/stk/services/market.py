"""Market service — indices, temperature, breadth."""

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import akshare as ak
from loguru import logger

from stk.deps import get_longport_ctx
from stk.errors import SourceError
from stk.models.market import IndexQuote, MarketBreadth, MarketTemperature
from stk.utils.price import r2

MAJOR_INDICES = [
    ("000001.SH", "上证指数"),
    ("399001.SZ", "深证成指"),
    ("399006.SZ", "创业板指"),
    ("HSI.HK", "恒生指数"),
    (".IXIC", "纳斯达克"),
    (".DJI", "道琼斯"),
    (".SPX", "标普500"),
]

_INDEX_NAMES = dict(MAJOR_INDICES)


def get_indices() -> list[IndexQuote]:
    """Get major index quotes from longport."""
    try:
        ctx = get_longport_ctx()
        symbols = [s for s, _ in MAJOR_INDICES]
        resp = ctx.quote(symbols)

        results = []
        for q in resp:
            last = r2(Decimal(str(q.last_done)))
            prev = Decimal(str(q.prev_close))
            change = r2(last - prev) if prev else None
            change_pct = r2(change / prev * 100) if (change is not None and prev) else None
            results.append(
                IndexQuote(
                    symbol=q.symbol,
                    name=_INDEX_NAMES.get(q.symbol, q.symbol),
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
    """Get market breadth from akshare (A-share)."""
    today = datetime.now(tz=ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d")

    try:
        # Count up/down/flat from A-share spot data
        df = ak.stock_zh_a_spot_em()
        up_count = int((df["涨跌幅"] > 0).sum())
        down_count = int((df["涨跌幅"] < 0).sum())
        flat_count = int((df["涨跌幅"] == 0).sum())

        # Limit up/down counts
        limit_up = 0
        limit_down = 0
        try:
            zt_df = ak.stock_zt_pool_em(date=today)
            limit_up = len(zt_df)
        except Exception:
            logger.debug("Failed to fetch limit-up pool, skipping")

        try:
            dt_df = ak.stock_zt_pool_dtgc_em(date=today)
            limit_down = len(dt_df)
        except Exception:
            logger.debug("Failed to fetch limit-down pool, skipping")

        return MarketBreadth(
            up_count=up_count,
            down_count=down_count,
            flat_count=flat_count,
            limit_up=limit_up,
            limit_down=limit_down,
        )
    except SourceError:
        raise
    except Exception as e:
        raise SourceError(f"Failed to fetch market breadth: {e}") from e
