"""Unified compact JSON envelope output for agent consumption."""

from datetime import datetime, timedelta, timezone
import json
from typing import Any

from pydantic import BaseModel


def _meta() -> dict[str, str]:
    cst = timezone(timedelta(hours=8))
    return {"generated_at": datetime.now(cst).isoformat(timespec="seconds")}


def render(data: object) -> None:
    """Print a successful envelope, omitting null model fields."""
    envelope = {
        "ok": True,
        "data": _serialize(data),
        "meta": _meta(),
    }
    print(json.dumps(envelope, ensure_ascii=False, default=str))


def render_error(code: str, message: str) -> None:
    """Print a request-level failure envelope."""
    envelope = {
        "ok": False,
        "error": {"code": code, "message": message},
        "meta": _meta(),
    }
    print(json.dumps(envelope, ensure_ascii=False))


def _serialize(obj: object) -> Any:
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json", exclude_none=True)
    if isinstance(obj, list):
        return [_serialize(item) for item in obj]
    return obj
