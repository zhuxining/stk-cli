"""Rank service — stock technical and popularity rankings."""

from collections.abc import Callable

import akshare as ak

from stk.errors import SourceError
from stk.models.market import TechRank, TechRankItem

_TechRankConfig = dict[str, str | Callable[[str], dict[str, str]]]

_TECH_RANK_CONFIG: dict[str, _TechRankConfig] = {
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

_SKIP_TECH_COLS = {"序号", "股票代码", "股票简称"}


def get_tech_rank(
    *,
    type: str = "lxsz",
    ma: str = "20 日均线",
) -> TechRank:
    """
    Get technical screening ranking from THS.

    type: lxsz (连续上涨) / cxfl (持续放量) / xstp (向上突破) / ljqs (量价齐升)
    ma: for xstp only — 5 日均线 / 10 日均线 / 20 日均线 / 60 日均线 / 250 日均线 etc.
    """
    cfg = _TECH_RANK_CONFIG.get(type)
    if not cfg:
        valid = "/".join(_TECH_RANK_CONFIG)
        raise SourceError(f"Unknown type: {type}, use {valid}")

    try:
        api_fn = getattr(ak, cfg["api"])  # type: ignore[arg-type]
        kwargs_fn = cfg["kwargs_fn"]
        df = api_fn(**kwargs_fn(ma))  # type: ignore[arg-type]

        if df.empty:
            raise SourceError(f"No {cfg['label']} data")

        items: list[TechRankItem] = []
        cols = [c for c in df.columns if c not in _SKIP_TECH_COLS]
        for _, row in df.iterrows():
            metrics = {c: str(row[c]) if row[c] is not None else None for c in cols}
            items.append(
                TechRankItem(
                    code=str(row["股票代码"]),
                    name=str(row["股票简称"]),
                    metrics=metrics,
                )
            )

        return TechRank(type=type, label=cfg["label"], items=items)  # type: ignore[arg-type]
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
