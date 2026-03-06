"""Decorator-driven cache with memory + optional disk persistence."""

from datetime import datetime
import functools
import hashlib
from pathlib import Path
import pickle
import time
from typing import Any
from zoneinfo import ZoneInfo

from loguru import logger

from stk.config import settings

# Module-level memory cache: key -> (expire_ts, value)
_mem_cache: dict[str, tuple[float, Any]] = {}

_CN_TZ = ZoneInfo("Asia/Shanghai")


def _is_market_hours() -> bool:
    """Check if current time is within A-share trading hours (CN 9:15-15:00, weekday)."""
    now = datetime.now(tz=_CN_TZ)
    if now.weekday() >= 5:  # weekend
        return False
    t = now.time()
    from datetime import time as dt_time

    return dt_time(9, 15) <= t <= dt_time(15, 0)


def _make_key(func: Any, args: tuple, kwargs: dict) -> str:
    """Build a unique cache key from function identity and arguments."""
    module = getattr(func, "__module__", "")
    name = getattr(func, "__qualname__", func.__name__)
    raw = repr((args, sorted(kwargs.items())))
    digest = hashlib.md5(raw.encode(), usedforsecurity=False).hexdigest()[:12]
    return f"{module}.{name}:{digest}"


def _cache_dir() -> Path:
    d = settings.cache_dir
    d.mkdir(parents=True, exist_ok=True)
    return d


def _disk_path(key: str) -> Path:
    safe = key.replace(".", "_").replace(":", "_")
    return _cache_dir() / f"{safe}.pkl"


def _read_disk(key: str) -> tuple[float, Any] | None:
    path = _disk_path(key)
    if not path.exists():
        return None
    try:
        data = pickle.loads(path.read_bytes())
        return data  # (expire_ts, value)
    except Exception:
        logger.debug("Disk cache read failed for {}, removing", key)
        path.unlink(missing_ok=True)
        return None


def _write_disk(key: str, expire_ts: float, value: Any) -> None:
    try:
        path = _disk_path(key)
        path.write_bytes(pickle.dumps((expire_ts, value)))
    except Exception:
        logger.debug("Disk cache write failed for {}", key)


def cached(ttl: int, *, disk: bool = False, market_hours_only: bool = False):
    """
    Cache decorator.

    Args:
        ttl: Time-to-live in seconds.
        disk: If True, also persist to disk (~/.stk/cache/).
        market_hours_only: If True, extend TTL 10x outside market hours.

    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not settings.cache_enabled:
                return func(*args, **kwargs)

            key = _make_key(func, args, kwargs)
            now = time.time()

            # 1. Check memory cache
            entry = _mem_cache.get(key)
            if entry and entry[0] > now:
                logger.debug("Cache HIT (mem): {}", key)
                return entry[1]

            # 2. Check disk cache
            if disk:
                entry = _read_disk(key)
                if entry and entry[0] > now:
                    logger.debug("Cache HIT (disk): {}", key)
                    _mem_cache[key] = entry
                    return entry[1]

            # 3. Call original function
            logger.debug("Cache MISS: {}", key)
            result = func(*args, **kwargs)

            # Compute effective TTL
            effective_ttl = ttl
            if market_hours_only and not _is_market_hours():
                effective_ttl = ttl * 10

            expire_ts = now + effective_ttl
            _mem_cache[key] = (expire_ts, result)
            if disk:
                _write_disk(key, expire_ts, result)

            return result

        return wrapper

    return decorator


def clear_cache(prefix: str = "") -> int:
    """Clear cache entries matching prefix. Returns count of cleared entries."""
    count = 0

    # Clear memory
    keys_to_remove = [k for k in _mem_cache if k.startswith(prefix)] if prefix else list(_mem_cache)
    for k in keys_to_remove:
        del _mem_cache[k]
        count += 1

    # Clear disk
    cache_dir = settings.cache_dir
    if cache_dir.exists():
        safe_prefix = prefix.replace(".", "_").replace(":", "_")
        for p in cache_dir.glob("*.pkl"):
            if not prefix or p.stem.startswith(safe_prefix):
                p.unlink(missing_ok=True)
                count += 1

    logger.info("Cleared {} cache entries (prefix='{}')", count, prefix)
    return count
