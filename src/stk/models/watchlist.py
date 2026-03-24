"""Watchlist models."""

from pydantic import BaseModel


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
