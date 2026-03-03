"""News service."""

from app.models.common import TargetType
from app.models.news import NewsItem


def get_news(
    symbol: str,
    *,
    target_type: TargetType = TargetType.STOCK,
    count: int = 10,
) -> list[NewsItem]:
    """Get recent news for a symbol."""
    # TODO: implement longport/akshare news fetching
    raise NotImplementedError("News service not yet implemented")
