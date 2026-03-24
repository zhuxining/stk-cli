"""Watchlist service — backed by longport watchlist API + local group ID cache."""

import time

from longport.openapi import SecuritiesUpdateMode, WatchlistGroup

from stk.deps import get_longport_ctx
from stk.errors import SourceError
from stk.models.watchlist import Watchlist, WatchlistSecurity, WatchlistSummary
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
            id=g.id, name=g.name, count=len(g.securities or []),
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


def add_symbols(name: str, symbols: list[str]) -> None:
    """Add one or more symbols to a watchlist group (batch)."""
    gid = _get_group_id(name)
    if gid is None:
        create_group(name, symbols=symbols)
        return
    ctx = get_longport_ctx()
    lp_symbols = [to_longport_symbol(s) for s in symbols]
    ctx.update_watchlist_group(
        id=gid,
        securities=lp_symbols,
        mode=SecuritiesUpdateMode.Add,
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
