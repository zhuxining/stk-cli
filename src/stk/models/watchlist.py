"""Watchlist models."""

from pydantic import BaseModel

from stk.models.scan import MonitorSummary


class WatchlistSecurity(BaseModel):
    """A security in a watchlist group."""

    symbol: str
    market: str = ""
    name: str = ""


class Watchlist(BaseModel):
    """User watchlist container."""

    id: int
    name: str
    securities: list[WatchlistSecurity] = []


class WatchlistSummary(BaseModel):
    """Watchlist group summary for list view."""

    id: int
    name: str
    count: int


class WorkflowResult(BaseModel):
    """Result of a watchlist workflow operation (scoop/route)."""

    action: str
    candidates_found: int = 0
    source_summary: MonitorSummary | None = None
    destinations: list[Watchlist] = []


class ZigzagSignal(BaseModel):
    """Zigzag pivot status for a single symbol."""

    symbol: str
    latest_pivot: str  # "high" or "low"
    pivot_price: float
    pivot_age: int  # bars since this pivot
