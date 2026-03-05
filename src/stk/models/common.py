"""Common models shared across domains."""

from enum import StrEnum

from pydantic import BaseModel


class TargetType(StrEnum):
    """Target type enumeration for symbol queries."""

    STOCK = "stock"
    SECTOR = "sector"
    CONCEPT = "concept"
    INDEX = "index"


class ErrorDetail(BaseModel):
    """Error response details."""

    type: str
    message: str


class ActionResult(BaseModel):
    """Result of a mutation action."""

    message: str


class Envelope(BaseModel):
    """Unified JSON response envelope."""

    ok: bool
    data: list | dict | None = None
    error: ErrorDetail | None = None
    meta: dict | None = None
