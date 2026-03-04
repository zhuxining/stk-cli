"""Unified JSON envelope output for agent consumption."""

import json
import sys
from typing import Any

from pydantic import BaseModel


def render(data: Any, *, meta: dict[str, Any] | None = None) -> None:
    """Print success JSON envelope to stdout."""
    serialized = [_serialize(item) for item in data] if isinstance(data, list) else _serialize(data)

    envelope = {"ok": True, "data": serialized, "error": None, "meta": meta or {}}
    print(json.dumps(envelope, ensure_ascii=False, default=str))


def render_error(error_type: str, message: str) -> None:
    """Print error JSON envelope to stdout and exit with code 1."""
    envelope = {
        "ok": False,
        "data": None,
        "error": {"type": error_type, "message": message},
    }
    print(json.dumps(envelope, ensure_ascii=False))
    sys.exit(1)


def _serialize(obj: Any) -> Any:
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    return obj
