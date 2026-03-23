"""Technical indicator models."""

from pydantic import BaseModel


class DailyResult(BaseModel):
    """OHLCV + all indicators merged per day."""

    symbol: str
    days: list[dict]
