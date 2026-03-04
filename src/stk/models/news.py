"""News models."""

from pydantic import BaseModel


class NewsItem(BaseModel):
    """News article item."""

    title: str
    source: str = ""
    url: str = ""
    published_at: str = ""
    summary: str = ""
