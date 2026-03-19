"""Watchlist scan service — batch quote + score + valuation + flow in one call."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal

from loguru import logger

from stk.models.flow import StockFlow
from stk.models.fundamental import Valuation
from stk.models.quote import Quote
from stk.models.scan import ScanItem, ScanResult
from stk.models.score import ScoreResult
from stk.services.flow import get_stock_flows
from stk.services.fundamental import get_valuations
from stk.services.longport_quote import get_realtime_quotes
from stk.services.score import calc_score
from stk.services.watchlist import get_watchlist
from stk.utils.price import r2


def _calc_net_main_flow(flow: StockFlow) -> Decimal | None:
    """Calculate net main flow in 万元 from a StockFlow object."""
    if flow.large_in is None or flow.large_out is None:
        return None
    net_large = flow.large_in - flow.large_out
    net_medium = (flow.medium_in or Decimal(0)) - (flow.medium_out or Decimal(0))
    return r2((net_large + net_medium) / 10000)


def _batch_analyze(
    symbols: list[str],
    names: dict[str, str],
    *,
    max_workers: int = 8,
) -> list[ScanItem]:
    """Batch analysis: quote + score + valuation + flow, all parallelized."""
    if not symbols:
        return []

    # 1. Batch quote — single API call
    quote_map: dict[str, Quote] = {}
    try:
        quotes = get_realtime_quotes(symbols)
        quote_map = {q.symbol: q for q in quotes}
        # Supplement names from quotes if not provided
        for q in quotes:
            if q.symbol not in names and q.name:
                names[q.symbol] = q.name
    except Exception as e:
        logger.warning(f"Batch quote failed: {e}")

    # 2. Batch valuation — single API call
    valuation_map: dict[str, Valuation] = {}
    try:
        valuations = get_valuations(symbols)
        valuation_map = {v.symbol: v for v in valuations}
    except Exception as e:
        logger.warning(f"Batch valuation failed: {e}")

    # 3. Parallel score calculation
    score_map: dict[str, ScoreResult] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(calc_score, s): s for s in symbols}
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                score_map[symbol] = future.result()
            except Exception as e:
                logger.debug(f"Score failed for {symbol}: {e}")

    # 4. Parallel flow (with cache) — skip ETFs
    from stk.utils.symbol import is_etf, to_longport_symbol

    non_etf_symbols = [s for s in symbols if not is_etf(s)]
    flow_map = get_stock_flows(non_etf_symbols, max_workers=max_workers) if non_etf_symbols else {}

    # 5. Assemble ScanItems
    items: list[ScanItem] = []
    for symbol in symbols:
        lp_sym = to_longport_symbol(symbol)
        q = quote_map.get(lp_sym)
        sc = score_map.get(symbol)
        v = valuation_map.get(lp_sym)
        fl = flow_map.get(lp_sym)

        change_pct = q.change_pct if q else None
        alerts: list[str] = []
        if change_pct is not None:
            cpct = float(change_pct)
            if cpct >= 5:
                alerts.append(f"大涨 ({cpct:+.1f}%)")
            elif cpct <= -3:
                alerts.append(f"大跌 ({cpct:.1f}%)")

        # RSI alerts from score
        if sc:
            for sig in sc.buy_signals:
                if "RSI超卖" in sig:
                    alerts.append(sig)
            for sig in sc.sell_signals:
                if "RSI超买" in sig:
                    alerts.append(sig)

        items.append(
            ScanItem(
                symbol=lp_sym,
                name=names.get(lp_sym, names.get(symbol, "")),
                last=q.last if q else None,
                change_pct=change_pct,
                source=q.source if q else "unknown",
                score=sc.total_score if sc else None,
                rating=sc.rating if sc else None,
                mode=sc.mode if sc else "stock",
                buy_signals=sc.buy_signals if sc else [],
                sell_signals=sc.sell_signals if sc else [],
                alerts=alerts,
                pe_ttm=v.pe_ttm_ratio if v else None,
                pb=v.pb_ratio if v else None,
                total_market_value=v.total_market_value if v else None,
                dividend_yield=v.dividend_ratio_ttm if v else None,
                volume_ratio=v.volume_ratio if v else None,
                net_main_flow=_calc_net_main_flow(fl) if fl else None,
            )
        )

    return items


def scan_watchlist(name: str, *, sort: str = "change_pct") -> ScanResult:
    """Fetch watchlist members, batch analyze all dimensions, return sorted results."""
    watchlist = get_watchlist(name)
    securities = watchlist.securities
    symbols = [s.symbol for s in securities]
    names_map = {s.symbol: s.name for s in securities}

    items = _batch_analyze(symbols, names_map)

    if sort == "score":
        items.sort(key=lambda x: x.score or 0, reverse=True)
    else:
        items.sort(key=lambda x: float(x.change_pct or 0), reverse=True)

    return ScanResult(group_name=name, total=len(items), items=items)


def batch_summary(symbols: list[str]) -> ScanResult:
    """Ad-hoc batch analysis for arbitrary symbols."""
    items = _batch_analyze(symbols, {})
    items.sort(key=lambda x: x.score or 0, reverse=True)

    return ScanResult(group_name="ad-hoc", total=len(items), items=items)
