"""Watchlist CRUD service."""

from stk.models.watchlist import Watchlist
from stk.store.file_store import load_json, save_json

WATCHLIST_FILE = "watchlist.json"


def list_watchlists() -> list[Watchlist]:
    """List all watchlists."""
    data = load_json(WATCHLIST_FILE)
    lists = data.get("lists", {})
    return [Watchlist(name=name, items=items) for name, items in lists.items()]


def get_watchlist(name: str) -> Watchlist:
    """Get a single watchlist by name."""
    data = load_json(WATCHLIST_FILE)
    items = data.get("lists", {}).get(name, [])
    return Watchlist(name=name, items=items)


def add_symbol(name: str, symbol: str) -> None:
    """Add a symbol to a watchlist."""
    data = load_json(WATCHLIST_FILE)
    lists = data.setdefault("lists", {})
    items = lists.setdefault(name, [])
    if symbol not in items:
        items.append(symbol)
    save_json(WATCHLIST_FILE, data)


def remove_symbol(name: str, symbol: str) -> None:
    """Remove a symbol from a watchlist."""
    data = load_json(WATCHLIST_FILE)
    lists = data.get("lists", {})
    if name in lists and symbol in lists[name]:
        lists[name].remove(symbol)
    save_json(WATCHLIST_FILE, data)
