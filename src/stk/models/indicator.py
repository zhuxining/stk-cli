"""Technical indicator models."""

from pydantic import BaseModel


class IndicatorResult(BaseModel):
    """Technical indicator calculation result."""

    symbol: str
    indicator: str
    params: dict | None = None
    values: list[dict]
