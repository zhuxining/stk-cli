"""Rank service — stock technical and popularity rankings."""

from collections.abc import Callable

import akshare as ak
from loguru import logger

from stk.errors import SourceError
from stk.models.market import (
    IndustryStats,
    TechCandidate,
    TechCandidates,
    TechHotspot,
    TechIndustries,
    TechRank,
    TechRankItem,
)
from stk.store.cache import cached

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
    "cxsl": {
        "api": "stock_rank_cxsl_ths",
        "label": "连续下跌",
        "kwargs_fn": lambda _ma: {},
    },
    "lxxd": {
        "api": "stock_rank_lxxd_ths",
        "label": "持续缩量",
        "kwargs_fn": lambda _ma: {},
    },
    "xxtp": {
        "api": "stock_rank_xxtp_ths",
        "label": "向下突破",
        "kwargs_fn": lambda ma: {"symbol": ma},
    },
    "ljqd": {
        "api": "stock_rank_ljqd_ths",
        "label": "量价齐跌",
        "kwargs_fn": lambda _ma: {},
    },
}

_SKIP_TECH_COLS = {"序号", "股票代码", "股票简称"}


@cached(ttl=28800)
def get_tech_rank(
    *,
    type: str = "lxsz",
    ma: str = "20 日均线",
) -> TechRank:
    """
    Get technical screening ranking from THS.

    type: lxsz (连续上涨) / cxfl (持续放量) / xstp (向上突破) / ljqs (量价齐升)
          cxsl (连续下跌) / lxxd (持续缩量) / xxtp (向下突破) / ljqd (量价齐跌)
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


# 行业分析用的 6 个 screen（有"所属行业"字段，排除 xstp/xxtp）
_BULL_INDUSTRY = {"lxsz", "cxfl", "ljqs"}
_BEAR_INDUSTRY = {"cxsl", "lxxd", "ljqd"}
_INDUSTRY_SCREENS = _BULL_INDUSTRY | _BEAR_INDUSTRY

# 技术选股：全部 4 个多方 / 4 个空方
_BULL_ALL = {"lxsz", "cxfl", "ljqs", "xstp"}
_BEAR_ALL = {"cxsl", "lxxd", "ljqd", "xxtp"}

_ALL_SCREENS = ["lxsz", "cxfl", "ljqs", "xstp", "cxsl", "lxxd", "ljqd", "xxtp"]

# 缩写 → 中文 label 映射
_SCREEN_LABEL: dict[str, str] = {
    k: str(v["label"]) for k, v in _TECH_RANK_CONFIG.items()
}


def _to_labels(codes: set[str] | list[str]) -> list[str]:
    """将 screen 缩写转为中文 label，按固定顺序排列。"""
    return [_SCREEN_LABEL[c] for c in _ALL_SCREENS if c in codes]


def get_tech_hotspot(ma: str = "20日均线") -> TechHotspot:
    """行业分析 + 多 screen 交叉验证选股。"""
    # 1. 串行获取 8 个 screen（akshare THS 内部用 V8，并发初始化会 crash）
    ranks: dict[str, TechRank] = {}
    for screen in _ALL_SCREENS:
        try:
            ranks[screen] = get_tech_rank(type=screen, ma=ma)
        except SourceError as e:
            logger.warning(f"Rank {screen} failed: {e}")

    # 2. 行业分析：统计每个行业在多空 screen 中的出现
    industry_bull: dict[str, set[str]] = {}  # industry -> {screen_types}
    industry_bear: dict[str, set[str]] = {}
    for screen_type, rank in ranks.items():
        if screen_type not in _INDUSTRY_SCREENS:
            continue
        is_bull = screen_type in _BULL_INDUSTRY
        for item in rank.items:
            industry = item.metrics.get("所属行业")
            if not industry:
                continue
            target = industry_bull if is_bull else industry_bear
            target.setdefault(industry, set()).add(screen_type)

    all_industries = set(industry_bull) | set(industry_bear)
    industries = sorted(
        [
            IndustryStats(
                industry=ind,
                bull_count=len(industry_bull.get(ind, set())),
                bear_count=len(industry_bear.get(ind, set())),
                bull_screens=_to_labels(industry_bull.get(ind, set())),
                bear_screens=_to_labels(industry_bear.get(ind, set())),
            )
            for ind in all_industries
        ],
        key=lambda x: (-x.bull_count, x.bear_count),
    )

    # 3. 技术选股：多方 screen 交叉验证
    stock_bull: dict[str, set[str]] = {}  # code -> {bull_screens}
    stock_bear: dict[str, set[str]] = {}  # code -> {bear_screens}
    stock_name: dict[str, str] = {}  # code -> name
    for screen_type, rank in ranks.items():
        is_bull = screen_type in _BULL_ALL
        for item in rank.items:
            stock_name[item.code] = item.name
            target = stock_bull if is_bull else stock_bear
            target.setdefault(item.code, set()).add(screen_type)

    # 只保留出现在 2+ 个多方 screen 且未出现在任何空方 screen 的股票
    candidates = sorted(
        [
            TechCandidate(
                code=code,
                name=stock_name[code],
                bull_screens=_to_labels(screens),
            )
            for code, screens in stock_bull.items()
            if len(screens) >= 3 and code not in stock_bear and "ST" not in stock_name[code]
        ],
        key=lambda x: -len(x.bull_screens),
    )

    return TechHotspot(
        industries=industries,
        candidates=candidates,
        total_candidates=len(candidates),
    )


def get_tech_industries(ma: str = "20日均线") -> TechIndustries:
    """行业多空分析（6 个有"所属行业"的 screen 统计）。"""
    h = get_tech_hotspot(ma=ma)
    return TechIndustries(industries=h.industries)


def get_tech_candidates(ma: str = "20日均线") -> TechCandidates:
    """交叉验证候选股（出现在 2+ 多方 screen）。"""
    h = get_tech_hotspot(ma=ma)
    return TechCandidates(candidates=h.candidates, total=h.total_candidates)
