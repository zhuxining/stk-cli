"""Historical candlestick data service."""

from app.models.common import TargetType
from app.models.history import Candlestick


def get_history(
    symbol: str,
    *,
    target_type: TargetType = TargetType.STOCK,
    period: str = "day",
    count: int = 30,
) -> list[Candlestick]:
    """Get historical candlestick data."""
    # TODO: implement data source calls
    raise NotImplementedError("History service not yet implemented")
