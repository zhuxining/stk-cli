"""Watchlist service — backed by longport watchlist API + local group ID cache."""

import contextlib
import time

from longport.openapi import SecuritiesUpdateMode, WatchlistGroup

from stk.deps import get_longport_ctx
from stk.errors import SourceError
from stk.models.scan import MonitorSummary
from stk.models.watchlist import Watchlist, WatchlistSecurity, WatchlistSummary, WorkflowResult
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


def scoop_candidates(name: str) -> WorkflowResult:
    """Scoop today's market candidates into a watchlist group.

    Gets tech candidates from THS, scans them for signal reference,
    and adds ALL candidates to the destination group.
    """
    from stk.services.rank import get_tech_candidates
    from stk.services.scan import batch_summary
    from stk.utils.symbol import expand_symbols

    candidates = get_tech_candidates()
    if not candidates.candidates:
        return WorkflowResult(action="scoop", candidates_found=0)

    symbols = expand_symbols([c.code for c in candidates.candidates])

    scan_result = batch_summary(symbols, include_daily10=False, include_full_context=False)

    add_symbols(name, symbols)

    return WorkflowResult(
        action="scoop",
        candidates_found=len(candidates.candidates),
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


def grid_candidates(src: str, dst: str) -> WorkflowResult:
    """Evaluate symbols in src group for grid trading suitability."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from loguru import logger

    from stk.services.indicator import get_daily

    watchlist = get_watchlist(src)
    symbols = [s.symbol for s in watchlist.securities]
    if not symbols:
        return WorkflowResult(action="grid", candidates_found=0)

    grid_symbols: list[str] = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(get_daily, s, count=60): s for s in symbols}
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                result = future.result()
                if _is_grid_candidate(result):
                    grid_symbols.append(symbol)
            except Exception as err:
                logger.debug(f"Grid check failed for {symbol}: {err}")

    if grid_symbols:
        add_symbols(dst, grid_symbols)

    return WorkflowResult(
        action="grid",
        candidates_found=len(symbols),
        source_summary=MonitorSummary(
            focus_count=len(grid_symbols),
            recommend_count=0,
            entry_signal_count=0,
            exit_signal_count=0,
            watch_signal_count=0,
        ),
        destinations=[get_watchlist(dst)] if grid_symbols else [],
    )


def _is_grid_candidate(daily_result: object) -> bool:
    """Check if a symbol is suitable for grid trading.

    Criteria:
    - ADX14 < 20 (no trend)
    - Bollinger bandwidth 10-50% (not too tight or wide)
    - RSI between 25-75 (not extreme)
    """
    if not hasattr(daily_result, "days") or not daily_result.days:  # type: ignore
        return False

    latest = daily_result.days[-1]  # type: ignore

    adx = latest.get("ADX14")
    if adx is None or adx >= 20:
        return False

    upper = latest.get("upper")
    lower = latest.get("lower")
    middle = latest.get("middle")
    if None in (upper, lower, middle) or middle == 0:
        return False
    bandwidth = (upper - lower) / middle * 100
    if bandwidth < 10 or bandwidth > 50:
        return False

    rsi = latest.get("RSI")
    return not (rsi is None or rsi <= 25 or rsi >= 75)
