"""Sync models — cross-platform watchlist sync data contracts."""

from pydantic import BaseModel


class SyncItem(BaseModel):
    """A single sync item: one stock to add or remove."""

    symbol: str
    """Longport symbol format."""
    action: str
    """Action: 'add', 'remove', or 'keep'."""
    ths_symbol: str = ""
    """THS symbol format (for THS sync)."""


class SyncDiff(BaseModel):
    """Difference between source and target groups."""

    from_group: str
    """Source group name (Longport for push/diff; THS for pull)."""
    to_group: str
    """Target group name (THS for push/diff; Longport for pull)."""
    to_add: list[SyncItem] = []
    """Symbols to add to target."""
    to_remove: list[SyncItem] = []
    """Symbols to remove from target."""
    unchanged: int = 0
    """Number of symbols already in sync."""


class SyncResult(BaseModel):
    """Result of a sync operation."""

    action: str
    """'push', 'pull', or 'diff'."""
    diff: SyncDiff
    added: int = 0
    """Number of symbols successfully added."""
    removed: int = 0
    """Number of symbols successfully removed."""
    errors: list[str] = []
    """Error messages for failed operations."""


class ThsGroup(BaseModel):
    """THS watchlist group summary."""

    name: str
    group_id: str
    count: int
    readonly: bool = False
