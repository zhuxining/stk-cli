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


class BoardItem(BaseModel):
    """Board (sector/concept) quote item."""

    code: str
    name: str
    metrics: dict[str, Decimal | None]


class BoardList(BaseModel):
    """Board listing result."""

    type: str  # "sector" / "concept"
    items: list[BoardItem]


class ConsItem(BaseModel):
    """A constituent stock in a board."""

    code: str
    name: str
    metrics: dict[str, Decimal | None]


class BoardCons(BaseModel):
    """Board constituent stocks."""

    board: str
    type: str  # "sector" / "concept"
    items: list[ConsItem]
