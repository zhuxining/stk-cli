"""Watchlist models."""

from pydantic import BaseModel


class WatchlistItem(BaseModel):
    symbol: str
    name: str = ""
    note: str = ""


class Watchlist(BaseModel):
    name: str
    items: list[str] = []
