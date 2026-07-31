"""Public models for ETF cross-sectional rotation."""

from typing import Literal

from pydantic import BaseModel, Field

type RotationStage = Literal["emerging", "leading", "weakening", "lagging"]
type RotationAction = Literal["exit", "rotate_in", "hold", "reduce", "watch", "avoid"]
type RotationTrend = Literal["bullish", "bearish", "neutral"]


class RotationFactors(BaseModel):
    return5: float
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
    turnover_ratio: float
    turnover_confirmation: float
    mfi_confirmation: float
    volume_confirmation: float


class RotationIndicators(BaseModel):
    close: float
    ema9: float
    ema20: float
    ema26: float
    ema60: float
    rsi14: float
    mfi14: float
    atr10: float
    atr_pct: float
    supertrend: float
    supertrend_bullish: bool


class RotationSignal(BaseModel):
    supertrend_bullish_event: bool = False
    supertrend_bearish_event: bool = False
    ema_golden_cross: bool = False
    ema_death_cross: bool = False
    entry_eligible: bool = False


class RotationItem(BaseModel):
    pool: str
    symbol: str
    name: str = ""
    as_of: str
    stage: RotationStage
    previous_stage: RotationStage | None = None
    stage_changed: bool
    action: RotationAction
    trend: RotationTrend
    strength: float
    momentum: float
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
    leading: int = 0
    weakening: int = 0
    lagging: int = 0


class RotationSummary(BaseModel):
    total: int
    analyzed: int
    failed: int
    emerging: int
    leading: int
    weakening: int
    lagging: int


class RotationFailure(BaseModel):
    pool: str
    symbol: str | None = None
    code: str
    message: str


class RotationResult(BaseModel):
    model: Literal["rotation_v1"] = "rotation_v1"
    sources: list[RotationPoolSummary]
    summary: RotationSummary
    emerging: list[RotationItem] = Field(default_factory=list)
    leading: list[RotationItem] = Field(default_factory=list)
    weakening: list[RotationItem] = Field(default_factory=list)
    lagging: list[RotationItem] = Field(default_factory=list)
    failures: list[RotationFailure] = Field(default_factory=list)


class RotationRouteTarget(BaseModel):
    stage: RotationStage
    group: str
    symbols: list[str] = Field(default_factory=list)


class RotationRouteResult(RotationResult):
    operation: Literal["rotate"] = "rotate"
    mode: Literal["replace"] = "replace"
    targets: list[RotationRouteTarget]
