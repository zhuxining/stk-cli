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
