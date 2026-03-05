"""Market service — indices, temperature, breadth via longport + akshare."""

from datetime import UTC, datetime
from decimal import Decimal

import akshare as ak
from loguru import logger

from stk.deps import get_longport_ctx
from stk.errors import SourceError
from stk.models.market import (
    IndexQuote,
    MarketBreadth,
    MarketTemperature,
    TechRank,
    TechRankItem,
)
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
    """Get market breadth from akshare (A-share)."""
    today = datetime.now(tz=UTC).strftime("%Y%m%d")

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


_TECH_RANK_CONFIG = {
    "lxsz": {
        "api": "stock_rank_lxsz_ths",
        "label": "连续上涨",
        "kwargs_fn": lambda _ma: {},
    },
    "cxfl": {
        "api": "stock_rank_cxfl_ths",
        "label": "持续放量",
        "kwargs_fn": lambda _ma: {},
    },
    "xstp": {
        "api": "stock_rank_xstp_ths",
        "label": "向上突破",
        "kwargs_fn": lambda ma: {"symbol": ma},
    },
    "ljqs": {
        "api": "stock_rank_ljqs_ths",
        "label": "量价齐升",
        "kwargs_fn": lambda _ma: {},
    },
}

_SKIP_COLS = {"序号", "股票代码", "股票简称"}


def get_tech_rank(
    *,
    type: str = "lxsz",
    ma: str = "20日均线",
) -> TechRank:
    """
    Get technical screening ranking from THS.

    type: lxsz (连续上涨) / cxfl (持续放量) / xstp (向上突破) / ljqs (量价齐升)
    ma: for xstp only — 5日均线 / 10日均线 / 20日均线 / 60日均线 / 250日均线 etc.
    """
    cfg = _TECH_RANK_CONFIG.get(type)
    if not cfg:
        valid = "/".join(_TECH_RANK_CONFIG)
        raise SourceError(f"Unknown type: {type}, use {valid}")

    try:
        api_fn = getattr(ak, cfg["api"])
        df = api_fn(**cfg["kwargs_fn"](ma))

        if df.empty:
            raise SourceError(f"No {cfg['label']} data")

        items: list[TechRankItem] = []
        cols = [c for c in df.columns if c not in _SKIP_COLS]
        for _, row in df.iterrows():
            metrics = {c: str(row[c]) if row[c] is not None else None for c in cols}
            items.append(
                TechRankItem(
                    code=str(row["股票代码"]),
                    name=str(row["股票简称"]),
                    metrics=metrics,
                )
            )

        return TechRank(type=type, label=cfg["label"], items=items)
    except SourceError:
        raise
    except Exception as e:
        raise SourceError(f"Failed to fetch {type} rank: {e}") from e


def get_hot_rank() -> TechRank:
    """Get stock popularity ranking from EastMoney."""
    try:
        df = ak.stock_hot_rank_em()
        if df.empty:
            raise SourceError("No hot rank data")

        items: list[TechRankItem] = []
        skip = {"当前排名", "代码", "股票名称"}
        cols = [c for c in df.columns if c not in skip]
        for _, row in df.iterrows():
            metrics = {c: str(row[c]) if row[c] is not None else None for c in cols}
            items.append(
                TechRankItem(
                    code=str(row["代码"]),
                    name=str(row["股票名称"]),
                    metrics=metrics,
                )
            )

        return TechRank(type="hot", label="人气榜", items=items)
    except SourceError:
        raise
    except Exception as e:
        raise SourceError(f"Failed to fetch hot rank: {e}") from e
