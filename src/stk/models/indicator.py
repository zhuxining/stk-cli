"""Technical indicator output models."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from stk.models.common import BatchFailure

type TrendDirection = Literal["bullish", "bearish"]


class KlinePeriod(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class KlineBar(BaseModel):
    """One chronological OHLCV bar with calculated indicators."""

    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    turnover: float | None = None
    change_pct: float | None = None
    ema5: float | None = None
    ema9: float | None = None
    ema10: float | None = None
    ema20: float | None = None
    ema26: float | None = None
    ema60: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_hist: float | None = None
    rsi14: float | None = None
    kdj_k: float | None = None
    kdj_d: float | None = None
    kdj_j: float | None = None
    wr14: float | None = None
    boll_upper: float | None = None
    boll_middle: float | None = None
    boll_lower: float | None = None
    atr10: float | None = None
    atr14: float | None = None
    supertrend: float | None = None
    supertrend_direction: TrendDirection | None = None


class KlineSeries(BaseModel):
    """K-line series for one symbol."""

    symbol: str
    bars: list[KlineBar] = Field(default_factory=list)


class KlineBatchResult(BaseModel):
    """Batch K-line command result."""

    period: KlinePeriod
    requested: int
    series: list[KlineSeries] = Field(default_factory=list)
    failures: list[BatchFailure] = Field(default_factory=list)
