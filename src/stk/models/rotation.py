"""Public models for ETF cross-sectional rotation."""

from typing import Literal

from pydantic import BaseModel, Field

type RotationStage = Literal["emerging", "strong", "fading"]
type RotationState = Literal["inactive", "emerging", "strong", "fading"]
type RotationAction = Literal["exit", "rotate_in", "hold", "reduce", "watch"]
type RotationSetup = Literal["rebound", "confirmed"]
type FadeSeverity = Literal["mild", "confirmed", "severe"]
type RotationTrend = Literal["bullish", "bearish", "neutral"]


class RotationFactors(BaseModel):
    return5: float
    previous_return5: float
    return20: float
    return60: float
    pool_median_return5: float
    pool_median_return20: float
    pool_median_return60: float
    vol20: float
    vol60: float
    adjusted_vol20: float
    adjusted_vol60: float
    current_excess5: float
    previous_excess5: float
    relative_momentum20: float
    relative_momentum60: float
    trend_quality: float
    acceleration: float
    ema20_slope5: float
    entry_distance_atr: float
    turnover_ratio: float
    turnover_confirmation: float
    mfi_confirmation: float
    volume_confirmation: float


class RotationIndicators(BaseModel):
    close: float
    ema5: float
    ema9: float
    ema10: float
    ema20: float
    ema26: float
    ema60: float
    rsi14: float
    adx14: float
    mfi14: float
    macd: float
    macd_signal: float
    macd_hist: float
    atr10: float
    atr_pct: float
    supertrend: float
    supertrend_bullish: bool


class RotationSignal(BaseModel):
    supertrend_bullish_event: bool = False
    supertrend_bearish_event: bool = False
    ema_golden_cross: bool = False
    ema_death_cross: bool = False
    supertrend_bullish_age: int | None = None
    supertrend_bearish_age: int | None = None
    ema_golden_cross_age: int | None = None
    ema_death_cross_age: int | None = None
    entry_eligible: bool = False


class RotationItem(BaseModel):
    pool: str
    symbol: str
    name: str = ""
    as_of: str
    stage: RotationStage
    previous_state: RotationState
    stage_changed: bool
    action: RotationAction
    trend: RotationTrend
    rank_score: float
    setup: RotationSetup | None = None
    fade_severity: FadeSeverity | None = None
    factors: RotationFactors
    indicators: RotationIndicators
    signal: RotationSignal
    warnings: list[str] = Field(default_factory=list)


class RotationPoolSummary(BaseModel):
    pool: str
    as_of: str | None = None
    total: int
    analyzed: int
    failed: int
    emerging: int = 0
    strong: int = 0
    fading: int = 0
    inactive: int = 0


class RotationSummary(BaseModel):
    total: int
    analyzed: int
    failed: int
    emerging: int
    strong: int
    fading: int
    inactive: int


class RotationFailure(BaseModel):
    pool: str
    symbol: str | None = None
    code: str
    message: str


class RotationResult(BaseModel):
    model: Literal["rotation_v2"] = "rotation_v2"
    sources: list[RotationPoolSummary]
    summary: RotationSummary
    emerging: list[RotationItem] = Field(default_factory=list)
    strong: list[RotationItem] = Field(default_factory=list)
    fading: list[RotationItem] = Field(default_factory=list)
    failures: list[RotationFailure] = Field(default_factory=list)


class RotationRouteTarget(BaseModel):
    stage: RotationStage
    group: str
    symbols: list[str] = Field(default_factory=list)


class RotationRouteResult(RotationResult):
    operation: Literal["rotate"] = "rotate"
    mode: Literal["replace"] = "replace"
    targets: list[RotationRouteTarget]
