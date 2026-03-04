"""Watchlist models."""

from pydantic import BaseModel


class WatchlistItem(BaseModel):
    """Watchlist item entry."""

    symbol: str
    name: str = ""
    note: str = ""


class Watchlist(BaseModel):
    """User watchlist container."""

    name: str
    items: list[str] = []
