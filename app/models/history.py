"""History / candlestick models."""

from decimal import Decimal

from pydantic import BaseModel


class Candlestick(BaseModel):
    date: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    turnover: Decimal | None = None
