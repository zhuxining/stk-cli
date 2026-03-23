"""Watchlist service — backed by longport watchlist API + local group ID cache."""

from longport.openapi import SecuritiesUpdateMode, WatchlistGroup

from stk.deps import get_longport_ctx
from stk.errors import SourceError
from stk.models.watchlist import Watchlist, WatchlistSecurity
from stk.store.file_store import load_json, save_json
from stk.utils.symbol import to_longport_symbol

_CACHE_FILE = "watchlist_groups.json"


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


def list_watchlists() -> list[Watchlist]:
    """List all watchlist groups from longport."""
    ctx = get_longport_ctx()
    groups = ctx.watchlist()
    result = [_to_watchlist(g) for g in groups]
    _sync_cache([{"name": g.name, "id": g.id} for g in groups])
    return result


def get_watchlist(name: str) -> Watchlist:
    """Get a single watchlist group by name."""
    ctx = get_longport_ctx()
    groups = ctx.watchlist()
    _sync_cache([{"name": g.name, "id": g.id} for g in groups])
    for g in groups:
        if g.name == name:
            return _to_watchlist(g)
    raise SourceError(f"Watchlist group '{name}' not found")


def create_group(name: str, symbols: list[str] | None = None) -> Watchlist:
    """Create a new watchlist group."""
    ctx = get_longport_ctx()
    securities = [to_longport_symbol(s) for s in symbols] if symbols else None
    group_id = ctx.create_watchlist_group(name=name, securities=securities)

    # Refresh cache
    groups = ctx.watchlist()
    _sync_cache([{"name": g.name, "id": g.id} for g in groups])

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
    # Update cache
    mapping = load_json(_CACHE_FILE)
    mapping.pop(name, None)
    save_json(_CACHE_FILE, mapping)
