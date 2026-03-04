"""Fundamental data models."""

from decimal import Decimal

from pydantic import BaseModel


class FinancialReport(BaseModel):
    """Financial report data."""

    symbol: str
    report_type: str  # income / balance / cashflow
    period: str
    items: dict[str, Decimal | str | None]


class Valuation(BaseModel):
    """Valuation metrics."""

    symbol: str
    pe: Decimal | None = None
    pb: Decimal | None = None
    ps: Decimal | None = None
    market_cap: Decimal | None = None
    total_shares: int | None = None
    float_shares: int | None = None


class Dividend(BaseModel):
    """Dividend information."""

    symbol: str
    ex_date: str
    amount: Decimal
    pay_date: str = ""
