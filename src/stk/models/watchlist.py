"""Longport group and routing output models."""

from typing import Literal

from pydantic import BaseModel, Field

from stk.models.common import BatchFailure, Platform


class WatchlistSecurity(BaseModel):
    symbol: str
    market: str = ""
    name: str = ""


class Watchlist(BaseModel):
    id: str
    name: str
    count: int
    securities: list[WatchlistSecurity] = Field(default_factory=list)


class WatchlistSummary(BaseModel):
    id: str
    name: str
    count: int
    readonly: bool | None = None


class GroupListResult(BaseModel):
    platform: Platform
    groups: list[WatchlistSummary] = Field(default_factory=list)


class GroupDetailResult(BaseModel):
    platform: Platform
    group: Watchlist


class RouteSource(BaseModel):
    platform: Literal["longport"] = "longport"
    group: str
    total: int
    analyzed: int
    failed: int


class RouteTarget(BaseModel):
    group: str
    symbols: list[str] = Field(default_factory=list)


class RouteTargets(BaseModel):
    buy: RouteTarget
    hold: RouteTarget
    sell: RouteTarget


class RouteResult(BaseModel):
    operation: Literal["route"] = "route"
    mode: Literal["replace", "append"]
    source: RouteSource
    targets: RouteTargets
    failures: list[BatchFailure] = Field(default_factory=list)
