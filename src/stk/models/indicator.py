"""Technical indicator models."""

from pydantic import BaseModel


class IndicatorResult(BaseModel):
    """Technical indicator calculation result."""

    symbol: str
    indicator: str
    params: dict | None = None
    values: list[dict]


class AllIndicatorsResult(BaseModel):
    """All indicators calculated in one pass."""

    symbol: str
    indicators: dict[str, list[dict]]


class DailyResult(BaseModel):
    """OHLCV + all indicators merged per day."""

    symbol: str
    days: list[dict]
