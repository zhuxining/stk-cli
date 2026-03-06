"""Price utility — Decimal rounding for financial display."""

from decimal import ROUND_HALF_UP, Decimal

_Q2 = Decimal("0.01")


def r2(v: Decimal) -> Decimal:
    """Round to 2 decimal places using ROUND_HALF_UP."""
    return v.quantize(_Q2, rounding=ROUND_HALF_UP)


def calc_change(last: Decimal, prev_close: Decimal) -> tuple[Decimal | None, Decimal | None]:
    """Calculate price change and change_pct, returns (change, change_pct)."""
    if not prev_close:
        return None, None
    change = r2(last - prev_close)
    change_pct = r2(change / prev_close * 100)
    return change, change_pct
