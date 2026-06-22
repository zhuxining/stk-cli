"""Watchlist service — backed by longport watchlist API + local group ID cache."""

import contextlib
import time

from longport.openapi import SecuritiesUpdateMode, WatchlistGroup

from stk.deps import get_longport_ctx
from stk.errors import SourceError
from stk.models.watchlist import (
    Watchlist,
    WatchlistSecurity,
    WatchlistSummary,
    WorkflowResult,
)
from stk.store.file_store import load_json, save_json
from stk.utils.symbol import to_longport_symbol

_CACHE_FILE = "watchlist_groups.json"

# In-memory cache for watchlist groups (avoid repeated full-list fetches)
_groups_cache: tuple[float, list[WatchlistGroup]] | None = None
_GROUPS_TTL = 60  # seconds


def _fetch_groups() -> list[WatchlistGroup]:
    """Fetch all groups with 60s in-memory cache."""
    global _groups_cache
    now = time.time()
    if _groups_cache and _groups_cache[0] > now:
        return _groups_cache[1]
    ctx = get_longport_ctx()
    groups = ctx.watchlist()
    _groups_cache = (now + _GROUPS_TTL, groups)
    _sync_cache([{"name": g.name, "id": g.id} for g in groups])
    return groups


def _invalidate_groups() -> None:
    """Invalidate groups cache after mutations."""
    global _groups_cache
    _groups_cache = None


def _sync_cache(groups: list[dict]) -> None:
    """Save group name→id mapping to local cache."""
    mapping = {g["name"]: g["id"] for g in groups}
    save_json(_CACHE_FILE, mapping)


def _get_group_id(name: str) -> int | None:
    """Lookup group id by name from local cache."""
    mapping = load_json(_CACHE_FILE)
    gid = mapping.get(name)
    return int(gid) if gid is not None else None


def _to_watchlist(group: WatchlistGroup) -> Watchlist:
    """Convert longport WatchlistGroup to model."""
    securities = [
        WatchlistSecurity(
            symbol=s.symbol,
            market=str(s.market),
            name=s.name or "",
        )
        for s in (group.securities or [])
    ]
    return Watchlist(id=group.id, name=group.name, securities=securities)


def list_watchlists() -> list[WatchlistSummary]:
    """List all watchlist groups (summary only)."""
    groups = _fetch_groups()
    return [
        WatchlistSummary(
            id=g.id,
            name=g.name,
            count=len(g.securities or []),
        )
        for g in groups
    ]


def get_watchlist(name: str) -> Watchlist:
    """Get a single watchlist group by name (60s cached)."""
    groups = _fetch_groups()
    for g in groups:
        if g.name == name:
            return _to_watchlist(g)
    raise SourceError(f"Watchlist group '{name}' not found")


def create_group(name: str, symbols: list[str] | None = None) -> Watchlist:
    """Create a new watchlist group."""
    ctx = get_longport_ctx()
    securities = [to_longport_symbol(s) for s in symbols] if symbols else None
    group_id = ctx.create_watchlist_group(name=name, securities=securities)

    _invalidate_groups()
    groups = _fetch_groups()

    for g in groups:
        if g.id == group_id:
            return _to_watchlist(g)
    return Watchlist(id=group_id, name=name, securities=[])


def add_symbols(name: str, symbols: list[str], mode: object = SecuritiesUpdateMode.Add) -> None:
    """Add/replace symbols in a watchlist group (batch).

    Args:
        name: Watchlist group name.
        symbols: Symbols to add/replace.
        mode: Add (append) or Replace (clear + set). Default Add.
    """
    gid = _get_group_id(name)
    if gid is None:
        create_group(name, symbols=symbols)
        return
    ctx = get_longport_ctx()
    lp_symbols = [to_longport_symbol(s) for s in symbols]
    ctx.update_watchlist_group(
        id=gid,
        securities=lp_symbols,
        mode=mode,
    )


def remove_symbols(name: str, symbols: list[str]) -> None:
    """Remove one or more symbols from a watchlist group (batch)."""
    gid = _get_group_id(name)
    if gid is None:
        raise SourceError(f"Watchlist group '{name}' not found")
    ctx = get_longport_ctx()
    lp_symbols = [to_longport_symbol(s) for s in symbols]
    ctx.update_watchlist_group(
        id=gid,
        securities=lp_symbols,
        mode=SecuritiesUpdateMode.Remove,
    )


def delete_group(name: str) -> None:
    """Delete a watchlist group."""
    gid = _get_group_id(name)
    if gid is None:
        raise SourceError(f"Watchlist group '{name}' not found")
    ctx = get_longport_ctx()
    ctx.delete_watchlist_group(id=gid)
    _invalidate_groups()
    mapping = load_json(_CACHE_FILE)
    mapping.pop(name, None)
    save_json(_CACHE_FILE, mapping)


_ENTRY_SIGNALS = {"趋势买入", "超卖修复"}
_EXIT_SIGNALS = {"趋势退出"}


def _filter_focus(focus: list, *, strict: bool) -> list[str]:
    """Filter scan focus items, returning symbols that pass the criteria.

    --scan: strength == "推荐"
    --scan --strict: 推荐 + bars_since_signal <= 2 + overall_bias == "supportive"
                     + risk_reward_ratio >= 1.5
    """
    MIN_STRICT_RR = 1.5
    MAX_STRICT_AGE = 2

    result: list[str] = []
    for item in focus:
        if item.decision.strength != "推荐":
            continue
        if strict:
            age = item.decision.bars_since_signal
            if age is None or age > MAX_STRICT_AGE:
                continue
            if item.context.overall_bias != "supportive":
                continue
            rr = item.risk.risk_reward_ratio
            if rr is None or rr < MIN_STRICT_RR:
                continue
        result.append(item.symbol)
    return result


def scoop_candidates(
    name: str, *, do_scan: bool = False, strict: bool = False, replace: bool = False
) -> WorkflowResult:
    """Scoop today's market candidates into a watchlist group.

    Without --scan: add all THS candidates directly.
    With --scan: filter by scan "推荐" signal before adding.
    With --scan --strict: tighter filters (new signal + supportive bias + RR≥1.5).

    Args:
        name: Destination watchlist group name.
        do_scan: If True, scan and filter signals.
        strict: If True, apply stricter filters (requires --scan).
        replace: Replace destination instead of appending.
    """
    from stk.services.rank import get_tech_candidates
    from stk.services.scan import batch_summary
    from stk.utils.symbol import expand_symbols

    candidates = get_tech_candidates()
    if not candidates.candidates:
        return WorkflowResult(action="scoop", candidates_found=0)

    symbols = expand_symbols([c.code for c in candidates.candidates])

    if not do_scan:
        mode = SecuritiesUpdateMode.Replace if replace else SecuritiesUpdateMode.Add
        add_symbols(name, symbols, mode=mode)
        return WorkflowResult(
            action="scoop",
            candidates_found=len(symbols),
            destinations=[get_watchlist(name)],
        )

    scan_result = batch_summary(symbols, include_daily10=False, include_full_context=False)
    recommended = _filter_focus(scan_result.focus, strict=strict)
    if not recommended:
        return WorkflowResult(
            action="scoop",
            candidates_found=0,
            source_summary=scan_result.summary,
        )

    mode = SecuritiesUpdateMode.Replace if replace else SecuritiesUpdateMode.Add
    add_symbols(name, recommended, mode=mode)

    return WorkflowResult(
        action="scoop",
        candidates_found=len(recommended),
        source_summary=scan_result.summary,
        destinations=[get_watchlist(name)],
    )


def hot_candidates(
    name: str,
    *,
    source: str = "rank",
    do_scan: bool = False,
    strict: bool = False,
    replace: bool = False,
) -> WorkflowResult:
    """Fetch EM hot stocks, optionally scan-filter, and add to a watchlist group.

    Without --scan: add all hot stocks directly.
    With --scan: filter by scan "推荐" signal before adding.
    With --scan --strict: tighter filters (new signal + supportive bias + RR≥1.5).

    Args:
        name: Destination watchlist group name.
        source: "rank" (热门排名) or "up" (热度上升).
        do_scan: If True, scan and filter signals.
        strict: If True, apply stricter filters (requires --scan).
        replace: Replace destination instead of appending.
    """
    from stk.errors import SourceError
    from stk.services.market import get_hot_rank, get_hot_up
    from stk.services.scan import batch_summary

    try:
        hot_result = get_hot_rank() if source == "rank" else get_hot_up()
    except SourceError:
        raise
    except Exception as e:
        raise SourceError(f"热门股获取失败 ({source}): {e}") from e

    if not hot_result.items:
        return WorkflowResult(action="hot", candidates_found=0)

    symbols = [item.symbol for item in hot_result.items]

    if not do_scan:
        mode = SecuritiesUpdateMode.Replace if replace else SecuritiesUpdateMode.Add
        add_symbols(name, symbols, mode=mode)
        return WorkflowResult(
            action="hot",
            candidates_found=len(symbols),
            destinations=[get_watchlist(name)],
        )

    scan_result = batch_summary(symbols, include_daily10=False, include_full_context=False)
    recommended = _filter_focus(scan_result.focus, strict=strict)
    if not recommended:
        return WorkflowResult(
            action="hot",
            candidates_found=0,
            source_summary=scan_result.summary,
        )

    mode = SecuritiesUpdateMode.Replace if replace else SecuritiesUpdateMode.Add
    add_symbols(name, recommended, mode=mode)

    return WorkflowResult(
        action="hot",
        candidates_found=len(recommended),
        source_summary=scan_result.summary,
        destinations=[get_watchlist(name)],
    )


def route_signals(
    src: str,
    entry_dst: str,
    exit_dst: str,
    *,
    replace: bool = False,
) -> WorkflowResult:
    """Scan a group and route entry/exit signals to destination groups."""
    from stk.services.scan import scan_watchlist

    scan_result = scan_watchlist(src, include_daily10=False, include_full_context=False)

    entry_symbols: list[str] = []
    exit_symbols: list[str] = []
    for item in scan_result.focus:
        signal = item.decision.signal
        if signal in _ENTRY_SIGNALS:
            entry_symbols.append(item.symbol)
        elif signal in _EXIT_SIGNALS:
            exit_symbols.append(item.symbol)

    mode = SecuritiesUpdateMode.Replace if replace else SecuritiesUpdateMode.Add

    if entry_symbols:
        add_symbols(entry_dst, entry_symbols, mode=mode)
    if exit_symbols:
        add_symbols(exit_dst, exit_symbols, mode=mode)

    destinations: list[Watchlist] = []
    with contextlib.suppress(SourceError):
        destinations.append(get_watchlist(entry_dst))
    with contextlib.suppress(SourceError):
        destinations.append(get_watchlist(exit_dst))

    return WorkflowResult(
        action="route",
        source_summary=scan_result.summary,
        destinations=destinations,
    )


def zigzag_picks(src: str, dst: str) -> WorkflowResult:
    """Find symbols with a zigzag pivot (high or low) in the last 5 bars."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from loguru import logger

    from stk.services.indicator import get_daily, zigzag_pivots

    watchlist = get_watchlist(src)
    symbols = [s.symbol for s in watchlist.securities]
    if not symbols:
        return WorkflowResult(action="zigzag", candidates_found=0)

    picks: list[str] = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(get_daily, s, count=60): s for s in symbols}
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                result = future.result()
                days = result.days
                days_rev = list(reversed(days))
                highs = [float(d["high"]) for d in days_rev if d.get("high") is not None]
                lows = [float(d["low"]) for d in days_rev if d.get("low") is not None]
                pivots = zigzag_pivots(highs, lows)
                if not pivots:
                    continue
                latest = pivots[-1]
                age = len(highs) - 1 - latest["index"]
                if age <= 5:
                    picks.append(symbol)
            except Exception as err:
                logger.debug(f"Zigzag failed for {symbol}: {err}")

    if picks:
        add_symbols(dst, picks)

    return WorkflowResult(
        action="zigzag",
        candidates_found=len(symbols),
        destinations=[get_watchlist(dst)] if picks else [],
    )
