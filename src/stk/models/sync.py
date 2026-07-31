"""Cross-platform group synchronization output models."""

from typing import Literal

from pydantic import BaseModel, Field

from stk.models.common import Platform

type SyncOperation = Literal["diff", "push", "pull"]
type SyncMode = Literal["preview", "merge", "replace"]


class SyncEndpoint(BaseModel):
    platform: Platform
    group: str


class SyncChanges(BaseModel):
    add_symbols: list[str] = Field(default_factory=list)
    remove_symbols: list[str] = Field(default_factory=list)
    unchanged_count: int = 0


class AppliedChanges(BaseModel):
    added_count: int = 0
    removed_count: int = 0


class SyncFailure(BaseModel):
    operation: Literal["add", "remove", "replace"]
    code: str
    message: str
    symbol: str | None = None


class SyncResult(BaseModel):
    operation: SyncOperation
    mode: SyncMode
    source: SyncEndpoint
    target: SyncEndpoint
    changes: SyncChanges
    applied: AppliedChanges | None = None
    failures: list[SyncFailure] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ThsGroup(BaseModel):
    id: str
    name: str
    count: int
    readonly: bool = False
