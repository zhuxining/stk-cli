"""Market service — indices, temperature, market overview."""

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import contextlib
from decimal import Decimal

from stk.deps import get_longport_ctx
from stk.errors import SourceError
from stk.models.market import IndexQuote, MarketOverview, MarketTemperature
from stk.utils.price import calc_change, r2

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
        futures = {
            executor.submit(_get_temperature_for_market, r): r
            for r in _MARKET_REGIONS
        }
        for future in as_completed(futures):
            region = futures[future]
            with contextlib.suppress(SourceError):
                temps[region] = future.result()

    return MarketOverview(indices=dict(grouped), temperature=temps)
