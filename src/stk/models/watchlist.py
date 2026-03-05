"""Watchlist models."""

from pydantic import BaseModel


class Watchlist(BaseModel):
    """User watchlist container."""

    name: str
    items: list[str] = []
