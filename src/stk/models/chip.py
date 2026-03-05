"""Chip distribution models."""

from decimal import Decimal

from pydantic import BaseModel


class ChipSlice(BaseModel):
    """Single chip cost distribution snapshot."""

    date: str
    cost_90_low: Decimal | None = None
    cost_90_high: Decimal | None = None
    cost_70_low: Decimal | None = None
    cost_70_high: Decimal | None = None
    concentration_70: Decimal | None = None


class ChipDistribution(BaseModel):
    """Chip distribution data for a security."""

    symbol: str
    avg_cost: Decimal | None = None
    profit_ratio: Decimal | None = None
    concentration: Decimal | None = None
    chips: list[ChipSlice] = []
