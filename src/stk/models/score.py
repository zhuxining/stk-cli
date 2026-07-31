"""Current daily signal assessment models."""

from typing import Literal

from pydantic import BaseModel, Field

type AssessmentState = Literal["buy", "sell", "watch", "ignored"]
type TrendDirection = Literal["bullish", "bearish", "neutral"]
type SignalTrigger = Literal[
    "healthy_continuation",
    "pullback_hold",
    "momentum_recovery",
    "trend_start",
    "supertrend_bearish",
    "ema26_breakdown",
    "overheat_reversal",
]
type ContextBias = Literal["supportive", "mixed", "conflicting", "risky"]
type FactorState = Literal["confirming", "neutral", "conflicting", "risk", "opportunity", "none"]
type MetricValue = str | int | float | bool | None


class ContextFactor(BaseModel):
    """One supporting or conflicting context factor."""

    name: str
    state: FactorState
    metrics: dict[str, MetricValue] = Field(default_factory=dict)


class QualitySummary(BaseModel):
    """Auxiliary signal quality."""

    bias: ContextBias
    warnings: list[str] = Field(default_factory=list)
    factors: list[ContextFactor] | None = None


class SignalIndicators(BaseModel):
    """Core values used to explain the current assessment."""

    close: float
    ema9: float
    ema26: float
    supertrend: float
    supertrend_direction: TrendDirection
    rsi14: float
    atr10: float
    adx14: float | None = None
    turnover_ratio_5d: float | None = None
    max_entry_price: float | None = None


class SignalRisk(BaseModel):
    """Buy-side loss-control boundaries."""

    stop_loss: float
    trailing_stop: float | None = None


class RecentSignalBar(BaseModel):
    """Compact confirmed bar attached to a signal on request."""

    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    turnover: float | None = None
    ema9: float | None = None
    ema26: float | None = None
    rsi14: float | None = None
    atr10: float | None = None
    supertrend: float | None = None
    supertrend_direction: TrendDirection | None = None


class StockAssessment(BaseModel):
    """Internal single-symbol result consumed by scan."""

    symbol: str
    as_of: str
    state: AssessmentState
    triggers: list[SignalTrigger] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    indicators: SignalIndicators
    quality: QualitySummary
    risk: SignalRisk | None = None
    recent_bars: list[RecentSignalBar] | None = None
