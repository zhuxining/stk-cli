"""News models."""

from pydantic import BaseModel


class NewsItem(BaseModel):
    title: str
    source: str = ""
    url: str = ""
    published_at: str = ""
    summary: str = ""
