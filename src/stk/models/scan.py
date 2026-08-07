"""Public scan output models."""

from decimal import Decimal

from pydantic import BaseModel, Field

from stk.models.common import BatchFailure
from stk.models.score import (
    QualitySummary,
    RecentSignalBar,
    SignalConfirmation,
    SignalIndicators,
    SignalRisk,
    SignalTrigger,
)


class QuoteSnapshot(BaseModel):
    """Optional realtime display data."""

    last: Decimal
    change_pct: Decimal | None = None
    source: str


class SignalDetail(BaseModel):
    """Current trigger and explanation; confirmation is None for non-event states."""

    confirmation: SignalConfirmation | None = None
    triggers: list[SignalTrigger] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class SignalItem(BaseModel):
    """One current buy or sell signal."""

    symbol: str
    name: str = ""
    as_of: str
    quote: QuoteSnapshot | None = None
    signal: SignalDetail
    indicators: SignalIndicators
    quality: QualitySummary
    risk: SignalRisk | None = None
    recent_bars: list[RecentSignalBar] | None = None


class ScanSummary(BaseModel):
    """Mutually exclusive scan coverage and state counts."""

    total: int
    analyzed: int
    failed: int
    buy: int
    sell: int
    watch: int
    hold: int = 0
    ignored: int


class ScanResult(BaseModel):
    """Current buy, hold, and sell signals for a Longport group."""

    group: str
    summary: ScanSummary
    buy: list[SignalItem] = Field(default_factory=list)
    hold: list[SignalItem] = Field(default_factory=list)
    sell: list[SignalItem] = Field(default_factory=list)
    failures: list[BatchFailure] = Field(default_factory=list)
