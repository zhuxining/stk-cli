"""Quote service — real-time quotes via longport."""

from stk.models.common import TargetType
from stk.models.quote import Quote


def get_quote(symbol: str, *, target_type: TargetType = TargetType.STOCK) -> Quote:
    """Get real-time quote via longport (stock/index) or akshare (sector/concept)."""
    if target_type in (TargetType.STOCK, TargetType.INDEX):
        from stk.services.longport_quote import get_realtime_quote

        return get_realtime_quote(symbol)

    raise NotImplementedError(f"Quote for {target_type} not yet implemented")
