"""Money flow service."""

from stk.models.common import TargetType
from stk.models.flow import MoneyFlow, SectorFlow


def get_flow(
    symbol: str,
    *,
    target_type: TargetType = TargetType.STOCK,
) -> MoneyFlow | SectorFlow:
    """Get money flow data."""
    # TODO: implement akshare fund flow data
    raise NotImplementedError("Flow service not yet implemented")
