"""Quote facade — all markets via longport."""

from stk.models.common import TargetType
from stk.models.quote import Quote


def get_quote(symbol: str, *, target_type: TargetType = TargetType.STOCK) -> Quote:
    """Get real-time quote via longport."""
    if target_type in (TargetType.STOCK, TargetType.INDEX):
        from stk.services.longport_quote import get_realtime_quote

        data = get_realtime_quote(symbol)
        return Quote(**data)

    # sector/concept — longport 无板块分类接口
    raise NotImplementedError(f"Quote for {target_type.value} not yet implemented (needs akshare)")
