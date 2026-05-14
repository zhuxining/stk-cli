"""Daily monitoring scan models."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from stk.models.score import Decision, PrimarySignal, RiskProfile, SignalContext

type FocusPriority = Literal["high", "medium", "low"]
type CompactDailyValue = str | int | float | None


class MonitorUniverse(BaseModel):
    """Universe coverage for a monitoring run."""

    name: str
    total: int
    scanned: int
    failed: int


class MonitorSummary(BaseModel):
    """Aggregated signal counts for a monitoring run."""

    focus_count: int
    high_priority_count: int
    entry_signal_count: int
    exit_signal_count: int
    watch_signal_count: int


class FocusItem(BaseModel):
    """One symbol selected for daily focus."""

    symbol: str
    name: str = ""
    priority: FocusPriority
    decision: Decision
    primary_signal: PrimarySignal
    context: SignalContext
    risk: RiskProfile
    last: Decimal | None = None
    change_pct: Decimal | None = None
    source: str = "unknown"
    daily10: list[dict[str, CompactDailyValue]] | None = None


class IgnoredSummary(BaseModel):
    """Symbols that were scanned but did not produce focus output."""

    no_signal_count: int


class ScanError(BaseModel):
    """Non-fatal per-symbol scan error."""

    symbol: str
    reason: str


class MonitorResult(BaseModel):
    """Daily monitoring result for a watchlist or ad-hoc universe."""

    run_date: str
    universe: MonitorUniverse
    summary: MonitorSummary
    focus: list[FocusItem] = Field(default_factory=list)
    ignored: IgnoredSummary
    errors: list[ScanError] = Field(default_factory=list)
