"""Quote facade — routes symbol to correct data source."""

import re

from stk.models.common import TargetType
from stk.models.quote import Quote


def get_quote(symbol: str, *, target_type: TargetType = TargetType.STOCK) -> Quote:
    """Get real-time quote, routing to the appropriate data source."""
    if target_type == TargetType.STOCK:
        data = _get_stock_quote(symbol)
    else:
        # TODO: implement sector/concept/index quote
        raise NotImplementedError(f"Quote for {target_type} not yet implemented")

    return Quote(**data)


def _get_stock_quote(symbol: str) -> dict:
    """Route stock symbol to longport or akshare."""
    if _is_hk_us(symbol):
        from stk.services.longport_quote import get_realtime_quote

        return get_realtime_quote(symbol)

    from stk.services.akshare_quote import get_realtime_quote

    return get_realtime_quote(symbol)


def _is_hk_us(symbol: str) -> bool:
    """Check if symbol is HK or US market."""
    return bool(re.search(r"\.(HK|US)$", symbol, re.IGNORECASE))
