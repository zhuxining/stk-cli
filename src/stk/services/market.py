"""Market service — indices, temperature, market overview, hot stocks."""

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import contextlib
from decimal import Decimal

import akshare as ak
from loguru import logger

from stk.deps import get_longport_ctx
from stk.errors import SourceError
from stk.models.market import (
    HotStockItem,
    HotStockResult,
    IndexQuote,
    MarketOverview,
    MarketTemperature,
)
from stk.store.cache import cached
from stk.utils.price import calc_change, r2
from stk.utils.symbol import from_em_symbol

MAJOR_INDICES = [
    ("000001.SH", "上证指数", "CN"),
    ("399001.SZ", "深证成指", "CN"),
    ("399006.SZ", "创业板指", "CN"),
    ("HSI.HK", "恒生指数", "HK"),
    ("HSCEI.HK", "国企指数", "HK"),
    ("HSTECH.HK", "恒生科技", "HK"),
    (".IXIC", "纳斯达克", "US"),
    (".DJI", "道琼斯", "US"),
    (".SPX", "标普500", "US"),
]

_INDEX_META = {s: (n, r) for s, n, r in MAJOR_INDICES}

_MARKET_REGIONS = {"CN": "CN", "HK": "HK", "US": "US"}


def get_indices() -> list[IndexQuote]:
    """Get major index quotes from longport."""
    try:
        ctx = get_longport_ctx()
        symbols = [s for s, _, _ in MAJOR_INDICES]
        resp = ctx.quote(symbols)

        results = []
        for q in resp:
            last = r2(Decimal(str(q.last_done)))
            prev = Decimal(str(q.prev_close))
            change, change_pct = calc_change(last, prev)
            name, region = _INDEX_META.get(q.symbol, (q.symbol, ""))
            results.append(
                IndexQuote(
                    symbol=q.symbol,
                    name=name,
                    region=region,
                    last=last,
                    change=change,
                    change_pct=change_pct,
                    volume=q.volume,
                )
            )
        return results
    except Exception as e:
        raise SourceError(f"Longport index API error: {e}") from e


def get_temperature() -> MarketTemperature:
    """Get market temperature from longport (CN market)."""
    return _get_temperature_for_market("CN")


def _get_temperature_for_market(region: str) -> MarketTemperature:
    """Get market temperature for a specific region."""
    from longport.openapi import Market

    market_map = {"CN": Market.CN, "HK": Market.HK, "US": Market.US}
    market = market_map.get(region)
    if market is None:
        raise SourceError(f"Unsupported market region: {region}")

    try:
        ctx = get_longport_ctx()
        resp = ctx.market_temperature(market)
        return MarketTemperature(
            score=resp.temperature,
            level=resp.description,
            valuation=resp.valuation,
            sentiment=resp.sentiment,
        )
    except Exception as e:
        raise SourceError(f"Longport temperature API error ({region}): {e}") from e


def _detect_regime(indices: list[IndexQuote]) -> str:
    """Detect market regime from index moves.

    Returns "trending" if most indices move >1% in the same direction,
    "ranging" if most are nearly flat (<0.5%), "mixed" otherwise.
    """
    if not indices:
        return "mixed"
    changes = [float(idx.change_pct) for idx in indices if idx.change_pct is not None]
    if not changes:
        return "mixed"

    up = sum(c > 1.0 for c in changes)
    down = sum(c < -1.0 for c in changes)
    flat = sum(abs(c) < 0.5 for c in changes)
    total = len(changes)

    if up >= total / 2 or down >= total / 2:
        return "trending"
    if flat >= total / 2:
        return "ranging"
    return "mixed"


def get_market_overview() -> MarketOverview:
    """Get combined market overview: grouped indices + temperature per region."""
    indices = get_indices()

    # Group indices by region
    grouped: dict[str, list[IndexQuote]] = defaultdict(list)
    for idx in indices:
        grouped[idx.region].append(idx)

    # Fetch temperature for all regions in parallel
    temps: dict[str, MarketTemperature] = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(_get_temperature_for_market, r): r for r in _MARKET_REGIONS}
        for future in as_completed(futures):
            region = futures[future]
            with contextlib.suppress(SourceError):
                temps[region] = future.result()

    regime = {r: _detect_regime(indices) for r, indices in grouped.items()}
    return MarketOverview(indices=dict(grouped), temperature=temps, regime=regime)


_HOT_STOCK_SKIP_COLS = {"最新价", "涨跌额", "涨跌幅"}


@cached(ttl=300, disk=True)
def get_hot_rank() -> HotStockResult:
    """东方财富热门个股排名（stock_hot_rank_em）。"""
    try:
        df = ak.stock_hot_rank_em()
    except Exception as e:
        raise SourceError(f"东方财富热门排名 API 失败: {e}") from e

    items = _parse_hot_stocks(df, source="rank")
    return HotStockResult(source="rank", items=items, total=len(items))


@cached(ttl=300, disk=True)
def get_hot_up() -> HotStockResult:
    """东方财富热度上升榜（stock_hot_up_em）。"""
    try:
        df = ak.stock_hot_up_em()
    except Exception as e:
        raise SourceError(f"东方财富热度上升榜 API 失败: {e}") from e

    items = _parse_hot_stocks(df, source="up")
    return HotStockResult(source="up", items=items, total=len(items))


def _parse_hot_stocks(df, *, source: str) -> list[HotStockItem]:
    """Parse akshare hot stock DataFrame into model items.

    Args:
        df: DataFrame with columns from stock_hot_rank_em or stock_hot_up_em.
        source: "rank" or "up".
    """
    items: list[HotStockItem] = []
    for _, row in df.iterrows():
        em_code = str(row["代码"])
        try:
            symbol = from_em_symbol(em_code)
        except Exception:
            logger.debug("Failed to convert EM symbol: {}", em_code)
            continue

        rank_change = None
        if source == "up":
            try:
                rank_change = int(row["排名较昨日变动"])
            except ValueError, TypeError:
                rank_change = None

        items.append(
            HotStockItem(
                rank=int(row["当前排名"]),
                symbol=symbol,
                name=str(row["股票名称"]),
                last=Decimal(str(row["最新价"])),
                change=Decimal(str(row["涨跌额"])),
                change_pct=Decimal(str(row["涨跌幅"])),
                rank_change=rank_change,
            )
        )
    return items
