"""Technical indicator models."""

from pydantic import BaseModel


class IndicatorResult(BaseModel):
    symbol: str
    indicator: str
    params: dict | None = None
    values: list[dict]
