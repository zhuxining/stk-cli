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
