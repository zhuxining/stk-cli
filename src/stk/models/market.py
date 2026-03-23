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
