"""News service — individual stock news + global market news."""

import akshare as ak

from stk.errors import SourceError
from stk.models.news import NewsItem
from stk.utils.symbol import extract_code, to_longport_symbol

# Column mapping: akshare column name → NewsItem field
_GLOBAL_SOURCE_CONFIG = {
    "cls": {
        "api": "stock_info_global_cls",
        "kwargs_fn": lambda f: {"symbol": f},
        "title": "标题",
        "summary": "内容",
        "published_at": "发布时间",
        "source_name": "财联社",
    },
    "ths": {
        "api": "stock_info_global_ths",
        "kwargs_fn": lambda _: {},
        "title": "标题",
        "summary": "内容",
        "published_at": "发布时间",
        "url": "链接",
        "source_name": "同花顺",
    },
    "em": {
        "api": "stock_info_global_em",
        "kwargs_fn": lambda _: {},
        "title": "标题",
        "summary": "摘要",
        "published_at": "发布时间",
        "url": "链接",
        "source_name": "东方财富",
    },
}


def get_news(symbol: str, *, count: int = 10) -> list[NewsItem]:
    """Get recent news for an individual stock (A-share)."""
    lp_symbol = to_longport_symbol(symbol)
    ak_symbol = extract_code(lp_symbol)

    try:
        df = ak.stock_news_em(symbol=ak_symbol)
        df = df.head(count)

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


def get_global_news(
    *,
    source: str = "cls",
    count: int = 20,
    filter_: str = "全部",
) -> list[NewsItem]:
    """
    Get global market news from cls/ths/em.

    source: cls (财联社) / ths (同花顺) / em (东方财富)
    filter_: for cls only — "全部" or "重点"
    """
    cfg = _GLOBAL_SOURCE_CONFIG.get(source)
    if not cfg:
        valid = "/".join(_GLOBAL_SOURCE_CONFIG)
        raise SourceError(f"Unknown source: {source}, use {valid}")

    try:
        api_fn = getattr(ak, cfg["api"])  # type: ignore[arg-type]
        kwargs = cfg["kwargs_fn"](filter_)  # type: ignore[misc]
        df = api_fn(**kwargs)

        if df.empty:
            raise SourceError(f"No global news from {source}")

        df = df.head(count)
        source_name = cfg["source_name"]

        items: list[NewsItem] = []
        for _, row in df.iterrows():
            # date column: cls has separate 发布日期+发布时间
            pub_at = str(row.get(cfg["published_at"], ""))
            if "发布日期" in row.index:
                pub_at = f"{row['发布日期']} {pub_at}"

            title = str(row.get(cfg["title"], ""))
            summary = str(row.get(cfg.get("summary", ""), ""))
            # CLS telegrams often have empty title — use content instead
            if not title and summary:
                title = summary[:80]

            items.append(
                NewsItem(
                    title=title,
                    summary=summary,
                    published_at=pub_at,
                    source=source_name,  # type: ignore[arg-type]
                    url=str(row.get(cfg.get("url", ""), "")),
                )
            )
        return items
    except SourceError:
        raise
    except Exception as e:
        raise SourceError(f"Failed to fetch global news from {source}: {e}") from e
