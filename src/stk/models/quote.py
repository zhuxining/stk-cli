"""Quote models."""

from decimal import Decimal

from pydantic import BaseModel


class Quote(BaseModel):
    """Real-time quote data."""

    symbol: str
    name: str = ""
    last: Decimal
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    prev_close: Decimal | None = None
    change: Decimal | None = None
    change_pct: Decimal | None = None
    volume: int | None = None
    turnover: Decimal | None = None
    timestamp: str | None = None
    source: str = "realtime"  # "realtime" | "last_close"
