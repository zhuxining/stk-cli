"""Watchlist scan service — batch quote + score + valuation + profile in one call."""

from concurrent.futures import ThreadPoolExecutor, as_completed

from loguru import logger

from stk.models.fundamental import Valuation
from stk.models.quote import Quote
from stk.models.scan import ScanItem, ScanResult
from stk.models.score import ScoreResult
from stk.services.fundamental import get_valuations
from stk.services.longport_quote import get_realtime_quotes
from stk.services.score import calc_score
from stk.services.watchlist import get_watchlist
from stk.utils.price import r2

_ALERT = "[警] "


def _batch_analyze(
    symbols: list[str],
    names: dict[str, str],
    *,
    max_workers: int = 8,
) -> list[ScanItem]:
    """Batch analysis: quote + score + valuation + profile, all parallelized."""
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

    # 4. Parallel profile (7-day disk cache, errors are non-fatal)
    from stk.services.fundamental import get_profile
    from stk.utils.symbol import to_longport_symbol

    profile_map: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures_p = {executor.submit(get_profile, s): s for s in symbols}
        for future in as_completed(futures_p):
            symbol = futures_p[future]
            try:
                profile = future.result()
                if profile.main_business:
                    lp_sym = to_longport_symbol(symbol)
                    profile_map[lp_sym] = profile.main_business
            except Exception as e:
                logger.debug(f"Profile failed for {symbol}: {e}")

    # 5. Assemble ScanItems
    items: list[ScanItem] = []
    for symbol in symbols:
        lp_sym = to_longport_symbol(symbol)
        q = quote_map.get(lp_sym)
        sc = score_map.get(symbol)
        v = valuation_map.get(lp_sym)

        # Merge signals: score signals + price alerts
        signals: list[str] = list(sc.signals) if sc else []
        change_pct = q.change_pct if q else None
        if change_pct is not None:
            cpct = float(change_pct)
            if cpct >= 5:
                signals.append(f"{_ALERT}大涨 ({cpct:+.1f}%)")
            elif cpct <= -3:
                signals.append(f"{_ALERT}大跌 ({cpct:.1f}%)")

        items.append(
            ScanItem(
                symbol=lp_sym,
                name=names.get(lp_sym, names.get(symbol, "")),
                last=q.last if q else None,
                change_pct=change_pct,
                source=q.source if q else "unknown",
                score=sc.total_score if sc else None,
                signals=signals,
                score_detail={d.name: d.signal for d in sc.dimensions if d.signal} if sc else {},
                pe_ttm=v.pe_ttm_ratio if v else None,
                pb=v.pb_ratio if v else None,
                dividend_yield=v.dividend_ratio_ttm if v else None,
                volume_ratio=v.volume_ratio if v else None,
                turnover_rate=v.turnover_rate if v else None,
                amplitude=v.amplitude if v else None,
                change_5d=v.five_day_change_rate if v else None,
                change_10d=v.ten_day_change_rate if v else None,
                ytd_change_rate=v.ytd_change_rate if v else None,
                adx=sc.adx if sc else None,
                atr=sc.atr if sc else None,
                stop_loss=sc.stop_loss if sc else None,
                take_profit=sc.take_profit if sc else None,
                risk_reward_ratio=sc.risk_reward_ratio if sc else None,
                capital_flow=r2(v.capital_flow / 10000) if v and v.capital_flow else None,
                main_business=profile_map.get(lp_sym),
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
