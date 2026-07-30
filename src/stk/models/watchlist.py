"""Watchlist models."""

from pydantic import BaseModel, Field

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
    securities: list[WatchlistSecurity] = Field(default_factory=list)


class WatchlistSummary(BaseModel):
    """Watchlist group summary for list view."""

    id: int
    name: str
    count: int


class WorkflowResult(BaseModel):
    """Result of a Longport signal routing operation."""

    action: str
    candidates_found: int = 0
    source_summary: MonitorSummary | None = None
    destinations: list[Watchlist] = Field(default_factory=list)
    buy: list[str] = Field(default_factory=list)
    sell: list[str] = Field(default_factory=list)
