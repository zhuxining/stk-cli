"""Technical indicator calculation service (ta-lib + pandas)."""

from stk.models.common import TargetType
from stk.models.indicator import IndicatorResult


def calc_indicator(
    symbol: str,
    indicator_name: str,
    *,
    target_type: TargetType = TargetType.STOCK,
    period: str = "day",
    count: int = 60,
) -> IndicatorResult:
    """Calculate a technical indicator for the given symbol."""
    # TODO: fetch history → apply ta-lib → return result
    raise NotImplementedError("Indicator service not yet implemented")
