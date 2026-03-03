"""Local JSON file storage under ~/.stk/."""

import json
from pathlib import Path
import tempfile
from typing import Any

from app.config import settings


def _ensure_dir() -> Path:
    """Ensure data directory exists and return it."""
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings.data_dir


def load_json(filename: str) -> dict[str, Any]:
    """Load a JSON file from data dir. Returns empty dict if not exists."""
    path = _ensure_dir() / filename
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(filename: str, data: Any) -> None:
    """Atomically save data as JSON to data dir."""
    dir_path = _ensure_dir()
    target = dir_path / filename

    # Atomic write: write to temp file then rename
    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=dir_path,
        suffix=".tmp",
        delete=False,
        encoding="utf-8",
    ) as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        tmp_path = Path(f.name)

    tmp_path.rename(target)
