"""Common public output models."""

from typing import Literal

from pydantic import BaseModel

type Platform = Literal["longport", "ths", "xueqiu"]


class ErrorDetail(BaseModel):
    """Request-level error."""

    code: str
    message: str


class BatchFailure(BaseModel):
    """One failed item in an otherwise successful batch."""

    code: str
    message: str
    symbol: str | None = None


class MutationResult(BaseModel):
    """Structured result for a group mutation."""

    operation: Literal["add", "remove", "delete"]
    platform: Platform
    group: str
    requested_symbols: list[str] | None = None
