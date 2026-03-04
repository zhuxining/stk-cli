"""Market / index models."""

from decimal import Decimal

from pydantic import BaseModel


class IndexQuote(BaseModel):
    """Market index quote data."""

    symbol: str
    name: str
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


class MarketBreadth(BaseModel):
    """Market breadth data."""

    up_count: int
    down_count: int
    flat_count: int = 0
    limit_up: int = 0
    limit_down: int = 0
