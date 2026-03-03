"""Common models shared across domains."""

from enum import StrEnum

from pydantic import BaseModel


class TargetType(StrEnum):
    STOCK = "stock"
    SECTOR = "sector"
    CONCEPT = "concept"
    INDEX = "index"


class ErrorDetail(BaseModel):
    type: str
    message: str


class Envelope(BaseModel):
    ok: bool
    data: list | dict | None = None
    error: ErrorDetail | None = None
    meta: dict | None = None
