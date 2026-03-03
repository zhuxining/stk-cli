"""Price utility — Decimal rounding for financial display."""

from decimal import ROUND_HALF_UP, Decimal

_Q2 = Decimal("0.01")


def r2(v: Decimal) -> Decimal:
    """Round to 2 decimal places using ROUND_HALF_UP."""
    return v.quantize(_Q2, rounding=ROUND_HALF_UP)
