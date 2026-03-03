"""Chip distribution service — longport has no chip/holder data."""

from stk.models.chip import ChipDistribution, HolderChange


def get_chip_distribution(symbol: str) -> ChipDistribution:
    """Get chip cost distribution. TODO: needs akshare — longport has no position cost data."""
    raise NotImplementedError("Chip distribution not yet implemented (needs akshare)")


def get_holder_change(symbol: str) -> list[HolderChange]:
    """Get shareholder count changes. TODO: needs akshare — longport has no holder data."""
    raise NotImplementedError("Holder change not yet implemented (needs akshare)")
