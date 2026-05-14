"""Stock monitoring signal models."""

from typing import Literal

from pydantic import BaseModel, Field

type SignalLevel = Literal["strong_buy", "buy", "hold", "sell", "strong_sell"]
type TrendDirection = Literal["bullish", "bearish", "neutral"]
type EmaCross = Literal["golden", "death"]
type SupertrendFlip = Literal["bullish", "bearish"]
type DecisionAction = Literal["focus_buy", "focus_sell", "watch"]
type SignalStatus = Literal["new", "active", "stale"]
type ContextBias = Literal["supportive", "mixed", "conflicting", "risky"]
type FactorState = Literal["confirming", "neutral", "conflicting", "risk", "opportunity", "none"]
type RiskLevel = Literal["low", "medium", "high"]
type MetricValue = str | int | float | bool | None


class TrendSignal(BaseModel):
    """Internal trend signal derived from EMA9/26 and Supertrend."""

    level: SignalLevel
    direction: TrendDirection
    confidence: float
    signal_date: str | None = None
    bars_since_signal: int | None = None
    ema9: float | None = None
    ema26: float | None = None
    supertrend: float | None = None
    supertrend_direction: TrendDirection = "neutral"
    ema_cross: EmaCross | None = None
    supertrend_flip: SupertrendFlip | None = None
    reasons: list[str] = Field(default_factory=list)


class Decision(BaseModel):
    """Monitoring decision used to select focus symbols."""

    action: DecisionAction
    level: SignalLevel
    direction: TrendDirection
    confidence: float
    signal_status: SignalStatus
    signal_date: str | None = None
    bars_since_signal: int | None = None


class PrimarySignal(BaseModel):
    """Raw evidence for the primary trend strategy."""

    ema_cross: EmaCross | None = None
    ema9: float | None = None
    ema26: float | None = None
    supertrend: float | None = None
    supertrend_direction: TrendDirection = "neutral"
    adx: float | None = None
    reasons: list[str] = Field(default_factory=list)


class ContextFactor(BaseModel):
    """One supporting or conflicting context factor."""

    name: str
    state: FactorState
    metrics: dict[str, MetricValue] = Field(default_factory=dict)


class SignalContext(BaseModel):
    """Auxiliary context derived from non-primary indicators."""

    overall_bias: ContextBias
    factors: list[ContextFactor] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RiskProfile(BaseModel):
    """ATR-based risk boundaries for a monitoring candidate."""

    atr: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    risk_reward_ratio: float | None = None
    risk_level: RiskLevel = "medium"


class ScoreResult(BaseModel):
    """Daily monitoring analysis for a single security."""

    symbol: str
    decision: Decision
    primary_signal: PrimarySignal
    context: SignalContext
    risk: RiskProfile
