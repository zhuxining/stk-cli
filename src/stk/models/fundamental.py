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
    # Warrant / Option fields
    expiry_date: str | None = None
    strike_price: Decimal | None = None
    upper_strike_price: Decimal | None = None
    lower_strike_price: Decimal | None = None
    outstanding_qty: int | None = None
    outstanding_ratio: Decimal | None = None
    premium: Decimal | None = None
    itm_otm: Decimal | None = None
    implied_volatility: Decimal | None = None
    warrant_delta: Decimal | None = None
    call_price: Decimal | None = None
    to_call_price: Decimal | None = None
    effective_leverage: Decimal | None = None
    leverage_ratio: Decimal | None = None
    conversion_ratio: Decimal | None = None
    balance_point: Decimal | None = None
    open_interest: int | None = None
    delta: Decimal | None = None
    gamma: Decimal | None = None
    theta: Decimal | None = None
    vega: Decimal | None = None
    rho: Decimal | None = None
