"""Money flow models."""

from decimal import Decimal

from pydantic import BaseModel


class FlowLine(BaseModel):
    """Intraday capital flow point (minute-level)."""

    timestamp: str
    inflow: Decimal


class StockFlow(BaseModel):
    """Individual stock money flow — realtime distribution + recent history."""

    symbol: str
    # Realtime distribution (longport)
    large_in: Decimal | None = None
    large_out: Decimal | None = None
    medium_in: Decimal | None = None
    medium_out: Decimal | None = None
    small_in: Decimal | None = None
    small_out: Decimal | None = None
    intraday: list[FlowLine] | None = None
