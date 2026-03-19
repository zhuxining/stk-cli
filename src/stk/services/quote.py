"""Quote service — real-time quotes via longport."""

from stk.models.common import TargetType
from stk.models.quote import Quote


def get_quote(symbol: str, *, target_type: TargetType = TargetType.STOCK) -> Quote:
    """Get real-time quote for a single symbol."""
    return get_quotes([symbol], target_type=target_type)[0]


def get_quotes(symbols: list[str], *, target_type: TargetType = TargetType.STOCK) -> list[Quote]:
    """Get real-time quotes for multiple symbols in a single API call."""
    if target_type in (TargetType.STOCK, TargetType.INDEX):
        from stk.services.longport_quote import get_realtime_quotes

        return get_realtime_quotes(symbols)

    raise NotImplementedError(f"Quote for {target_type} not yet implemented")
