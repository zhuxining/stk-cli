"""Chip distribution service (A-share only)."""

from app.models.chip import ChipDistribution, HolderChange


def get_chip_distribution(symbol: str) -> ChipDistribution:
    """Get chip cost distribution."""
    # TODO: implement akshare chip data
    raise NotImplementedError("Chip distribution service not yet implemented")


def get_holder_change(symbol: str) -> list[HolderChange]:
    """Get shareholder count changes."""
    # TODO: implement akshare holder data
    raise NotImplementedError("Holder change service not yet implemented")
