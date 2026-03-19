"""Stock scoring models."""

from pydantic import BaseModel


class ScoreDimension(BaseModel):
    """A single scoring dimension with score and signal."""

    name: str
    score: float
    max_score: float
    signal: str | None = None


class ScoreResult(BaseModel):
    """Multi-indicator resonance scoring result."""

    symbol: str
    total_score: float
    rating: str  # A+ / A / B+ / B / C
    dimensions: list[ScoreDimension]
    buy_signals: list[str]
    sell_signals: list[str]
    mode: str = "stock"  # "stock" | "etf"
    # ADX trend strength context
    trend_strength: str | None = None  # "trending" | "ranging" | None
    adx: float | None = None
    # ATR-based trade points (optional, A-share only when history available)
    atr: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    risk_reward_ratio: float | None = None
