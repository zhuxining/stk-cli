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


class HolderChange(BaseModel):
    """Holder count change data."""

    date: str
    holder_count: int
    avg_shares: Decimal | None = None
    change_pct: Decimal | None = None
