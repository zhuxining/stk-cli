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
    dimensions: list[ScoreDimension]
    signals: list[str]  # "[买] ..." / "[卖] ..."
    adx: float | None = None
    # ATR-based trade points
    atr: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    risk_reward_ratio: float | None = None
