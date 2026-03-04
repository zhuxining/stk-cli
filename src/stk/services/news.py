"""News service."""

import akshare as ak

from stk.errors import SourceError
from stk.models.common import TargetType
from stk.models.news import NewsItem
from stk.services.symbol import to_longport_symbol


def get_news(
    symbol: str,
    *,
    target_type: TargetType = TargetType.STOCK,
    count: int = 10,
) -> list[NewsItem]:
    """
    Get recent news for a symbol.

    Args:
        symbol: Stock symbol (e.g., "600519", "700.HK", "AAPL.US")
        target_type: Target type (only STOCK is supported)
        count: Number of news items to return (default 10)

    Returns:
        List of NewsItem objects

    Raises:
        NotImplementedError: If target_type is not STOCK
        SourceError: If news fetching fails

    """
    if target_type != TargetType.STOCK:
        raise NotImplementedError(f"News for {target_type.value} not yet implemented")

    # Convert to longport format, then extract pure code for akshare
    lp_symbol = to_longport_symbol(symbol)

    # akshare expects pure stock code without market suffix
    # e.g., "600519.SH" -> "600519", "000001.SZ" -> "000001"
    ak_symbol = lp_symbol.split(".")[0] if "." in lp_symbol else lp_symbol

    try:
        df = ak.stock_news_em(symbol=ak_symbol)

        # Limit to requested count
        df = df.head(count)

        # Convert DataFrame to NewsItem list
        return [
            NewsItem(
                title=row["新闻标题"],
                summary=row["新闻内容"],
                published_at=row["发布时间"],
                source=row["文章来源"],
                url=row["新闻链接"],
            )
            for _, row in df.iterrows()
        ]

    except Exception as e:
        raise SourceError(f"Failed to fetch news for {symbol}: {e}") from e
