"""Market / index models."""

from decimal import Decimal

from pydantic import BaseModel


class IndexQuote(BaseModel):
    """Market index quote data."""

    symbol: str
    name: str
    region: str  # "CN" / "HK" / "US"
    last: Decimal
    change: Decimal | None = None
    change_pct: Decimal | None = None
    volume: int | None = None


class MarketTemperature(BaseModel):
    """Market temperature sentiment score."""

    score: int  # 0-100 temperature value
    level: str  # description from longport (e.g. 冰点/偏冷/中性/偏热/沸点)
    valuation: int | None = None
    sentiment: int | None = None


class MarketOverview(BaseModel):
    """Combined market indices + temperature by region."""

    indices: dict[str, list[IndexQuote]]  # {"CN": [...], "HK": [...], "US": [...]}
    temperature: dict[str, MarketTemperature]  # {"CN": ..., "HK": ..., "US": ...}


class TechRankItem(BaseModel):
    """A stock in technical screening ranking."""

    code: str
    name: str
    metrics: dict[str, str | None]


class TechRank(BaseModel):
    """Technical screening ranking result."""

    type: str  # lxsz / cxfl / xstp / ljqs
    label: str  # 连续上涨 / 持续放量 / 向上突破 / 量价齐升
    items: list[TechRankItem]


class IndustryStats(BaseModel):
    """行业在多空 screen 中的出现统计。"""

    industry: str
    bull_count: int  # 出现在多方 screen 的次数
    bear_count: int  # 出现在空方 screen 的次数
    bull_screens: list[str]  # 哪些多方 screen
    bear_screens: list[str]  # 哪些空方 screen


class TechCandidate(BaseModel):
    """在 2+ 个多方 screen 同时出现的候选股。"""

    code: str
    name: str
    bull_screens: list[str]  # 出现在哪些多方 screen


class TechHotspot(BaseModel):
    """行业分析 + 技术选股候选。"""

    industries: list[IndustryStats]  # 按 bull_count 降序
    candidates: list[TechCandidate]  # 在 2+ 多方 screen 的股票
    total_candidates: int


class TechIndustries(BaseModel):
    """行业多空分析结果。"""

    industries: list[IndustryStats]


class TechCandidates(BaseModel):
    """交叉验证候选股。"""

    candidates: list[TechCandidate]
    total: int
