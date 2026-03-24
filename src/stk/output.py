"""Unified JSON envelope output for agent consumption."""

from datetime import datetime, timedelta, timezone
import json
from typing import Any

from pydantic import BaseModel


def render(data: Any, *, meta: dict[str, Any] | None = None) -> None:
    """Print success JSON envelope to stdout."""
    serialized = [_serialize(item) for item in data] if isinstance(data, list) else _serialize(data)

    cst = timezone(timedelta(hours=8))
    combined_meta = {"updated_at": datetime.now(cst).isoformat(timespec="seconds")}
    if meta:
        combined_meta.update(meta)
    envelope = {"ok": True, "data": serialized, "error": None, "meta": combined_meta}
    print(json.dumps(envelope, ensure_ascii=False, default=str))


def render_error(error_type: str, message: str) -> None:
    """Print error JSON envelope to stdout."""
    envelope = {
        "ok": False,
        "data": None,
        "error": {"type": error_type, "message": message},
        "meta": {},
    }
    print(json.dumps(envelope, ensure_ascii=False))


def _serialize(obj: Any) -> Any:
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    return obj
