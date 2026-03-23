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


class FullComparison(BaseModel):
    """All industry comparison categories for a stock."""

    symbol: str
    comparisons: list[IndustryComparison]


class CompanyProfile(BaseModel):
    """Company main business profile."""

    symbol: str
    main_business: str = ""
    product_type: str = ""
    product_name: str = ""
    business_scope: str = ""


class Valuation(BaseModel):
    """Valuation metrics from longport calc_indexes."""

    symbol: str
    last_done: Decimal | None = None
    change_value: Decimal | None = None
    change_rate: Decimal | None = None
    volume: int | None = None
    turnover: Decimal | None = None
    ytd_change_rate: Decimal | None = None
    turnover_rate: Decimal | None = None
    total_market_value: Decimal | None = None
    capital_flow: Decimal | None = None
    amplitude: Decimal | None = None
    volume_ratio: Decimal | None = None
    pe_ttm_ratio: Decimal | None = None
    pb_ratio: Decimal | None = None
    dividend_ratio_ttm: Decimal | None = None
    five_day_change_rate: Decimal | None = None
    ten_day_change_rate: Decimal | None = None
    half_year_change_rate: Decimal | None = None
    five_minutes_change_rate: Decimal | None = None
