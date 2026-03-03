"""Market / index models."""

from decimal import Decimal

from pydantic import BaseModel


class IndexQuote(BaseModel):
    symbol: str
    name: str
    last: Decimal
    change: Decimal | None = None
    change_pct: Decimal | None = None
    volume: int | None = None


class MarketTemperature(BaseModel):
    score: int  # 0-100
    level: str  # 冰点/偏冷/中性/偏热/沸点
    details: list[dict]


class MarketBreadth(BaseModel):
    up_count: int
    down_count: int
    flat_count: int = 0
    limit_up: int = 0
    limit_down: int = 0
