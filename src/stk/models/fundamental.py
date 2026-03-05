"""Fundamental data models."""

from decimal import Decimal

from pydantic import BaseModel


class CompanyMetric(BaseModel):
    """A single company's metrics in an industry comparison."""

    code: str  # "600519" or "行业平均"/"行业中值"
    name: str
    metrics: dict[str, Decimal | None]


class IndustryComparison(BaseModel):
    """Industry comparison result — stock vs peers."""

    symbol: str
    category: str  # "growth" / "valuation" / "dupont"
    companies: list[CompanyMetric]


class Valuation(BaseModel):
    """Valuation metrics."""

    symbol: str
    pe: Decimal | None = None
    pb: Decimal | None = None
    ps: Decimal | None = None
    market_cap: Decimal | None = None
    total_shares: int | None = None
    float_shares: int | None = None
