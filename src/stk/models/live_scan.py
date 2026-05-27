"""Intraday live scan models."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from stk.models.scan import MonitorUniverse, ScanError
from stk.models.score import DecisionSignal, SignalStrength

type LiveSignal = Literal["实时跟随", "实时转弱", "实时过热", "实时观察"]
type LiveStrength = Literal["强提醒", "普通提醒", "观察"]


class LiveFocusItem(BaseModel):
    """One symbol selected by intraday scan."""

    symbol: str
    name: str = ""
    daily_signal: DecisionSignal
    daily_strength: SignalStrength
    live_signal: LiveSignal
    strength: LiveStrength
    trigger: str
    last: Decimal | None = None
    change_pct: Decimal | None = None
    risk_line: float | None = None
    volume_ratio: float | None = None
    vwap: float | None = None
    ema20: float | None = None
    rsi14: float | None = None


class LiveScanSummary(BaseModel):
    """Aggregated intraday signal counts."""

    focus_count: int
    follow_count: int
    weaken_count: int
    overheated_count: int
    observe_count: int


class LiveIgnoredSummary(BaseModel):
    """Symbols scanned but not selected by intraday scan."""

    no_live_signal_count: int


class LiveScanResult(BaseModel):
    """Intraday scan result for a symbol list or watchlist."""

    mode: Literal["live"] = "live"
    as_of: str
    timeframe: str
    universe: MonitorUniverse
    summary: LiveScanSummary
    focus: list[LiveFocusItem] = Field(default_factory=list)
    ignored: LiveIgnoredSummary
    errors: list[ScanError] = Field(default_factory=list)
