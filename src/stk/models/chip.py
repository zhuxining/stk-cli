"""Chip distribution models."""

from decimal import Decimal

from pydantic import BaseModel


class ChipDistribution(BaseModel):
    """Chip distribution data for a security."""

    symbol: str
    avg_cost: Decimal | None = None
    profit_ratio: Decimal | None = None
    concentration: Decimal | None = None
    chips: list[dict] = []
