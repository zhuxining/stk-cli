"""Fundamental data models."""

from decimal import Decimal

from pydantic import BaseModel


class FinancialReport(BaseModel):
    symbol: str
    report_type: str  # income / balance / cashflow
    period: str
    items: dict[str, Decimal | str | None]


class Valuation(BaseModel):
    symbol: str
    pe: Decimal | None = None
    pb: Decimal | None = None
    ps: Decimal | None = None
    market_cap: Decimal | None = None
    total_shares: int | None = None
    float_shares: int | None = None


class Dividend(BaseModel):
    symbol: str
    ex_date: str
    amount: Decimal
    pay_date: str = ""
