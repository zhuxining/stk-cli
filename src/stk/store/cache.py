"""Decorator-driven cache with memory LRU + optional disk persistence."""

from collections import OrderedDict
from datetime import datetime
import functools
import hashlib
from pathlib import Path
import pickle
import random
import threading
import time
from typing import Any
from zoneinfo import ZoneInfo

from loguru import logger

from stk.config import settings

# ---------------------------------------------------------------------------
# Cache limits
# ---------------------------------------------------------------------------
_MAX_MEM_ENTRIES = 1000
_MAX_DISK_FILES = 500
_MAX_DISK_SIZE_MB = 50

# Module-level LRU memory cache: OrderedDict[key, (expire_ts, value)]
_mem_cache: OrderedDict[str, tuple[float, Any]] = OrderedDict()
_cache_lock = threading.Lock()

# Global disable switch (set by --no-cache CLI flag)
_cache_force_disabled = False

_CN_TZ = ZoneInfo("Asia/Shanghai")


def disable() -> None:
    """Force-disable all caching (used by --no-cache flag)."""
    global _cache_force_disabled
    _cache_force_disabled = True


def _is_cache_enabled() -> bool:
    return settings.cache_enabled and not _cache_force_disabled


def _is_market_hours() -> bool:
    """Check if current time is within A-share trading hours (CN 9:15-15:00, weekday)."""
    now = datetime.now(tz=_CN_TZ)
    if now.weekday() >= 5:  # weekend
        return False
    from datetime import time as dt_time

    return dt_time(9, 15) <= t <= dt_time(15, 0)


def _make_key(func: Any, args: tuple, kwargs: dict) -> str:
    """Build a unique cache key from function identity and arguments."""
    module = getattr(func, "__module__", "")
    name = getattr(func, "__qualname__", func.__name__)
    raw = repr((args, sorted(kwargs.items())))
    digest = hashlib.md5(raw.encode(), usedforsecurity=False).hexdigest()[:12]
    return f"{module}.{name}:{digest}"


# ---------------------------------------------------------------------------
# Memory cache (LRU, thread-safe)
# ---------------------------------------------------------------------------


def _mem_get(key: str) -> tuple[float, Any] | None:
    """Thread-safe memory cache lookup with LRU promotion."""
    with _cache_lock:
        entry = _mem_cache.get(key)
        if entry is not None:
            _mem_cache.move_to_end(key)
        return entry


def _mem_set(key: str, expire_ts: float, value: Any) -> None:
    """Thread-safe memory cache write with LRU eviction."""
    with _cache_lock:
        if key in _mem_cache:
            _mem_cache.move_to_end(key)
        _mem_cache[key] = (expire_ts, value)
        while len(_mem_cache) > _MAX_MEM_ENTRIES:
            evicted_key, _ = _mem_cache.popitem(last=False)
            logger.debug("Cache LRU evict (mem): {}", evicted_key)


def _mem_clear(prefix: str = "") -> int:
    """Clear memory cache entries matching prefix. Returns count."""
    with _cache_lock:
        keys = [k for k in _mem_cache if k.startswith(prefix)] if prefix else list(_mem_cache)
        for k in keys:
            del _mem_cache[k]
    return len(keys)


def _mem_stats() -> dict:
    """Return memory cache statistics."""
    with _cache_lock:
        entries = len(_mem_cache)
        by_module: dict[str, int] = {}
        for key, (_expire_ts, _value) in _mem_cache.items():
            module = key.split(":")[0].rsplit(".", 1)[0]
            by_module[module] = by_module.get(module, 0) + 1
    return {"entries": entries, "max": _MAX_MEM_ENTRIES, "by_module": by_module}


# ---------------------------------------------------------------------------
# Disk cache
# ---------------------------------------------------------------------------


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


def _evict_disk_if_needed() -> None:
    """Remove oldest disk cache files if limits exceeded."""
    cache_dir = settings.cache_dir
    if not cache_dir.exists():
        return

    files = sorted(cache_dir.glob("*.pkl"), key=lambda p: p.stat().st_mtime)
    total_size = sum(f.stat().st_size for f in files)

    # Evict by count
    while len(files) > _MAX_DISK_FILES:
        oldest = files.pop(0)
        oldest.unlink(missing_ok=True)
        total_size -= oldest.stat().st_size if oldest.exists() else 0
        logger.debug("Cache LRU evict (disk): {}", oldest.stem)

    # Evict by size
    max_bytes = _MAX_DISK_SIZE_MB * 1024 * 1024
    while total_size > max_bytes and files:
        oldest = files.pop(0)
        size = oldest.stat().st_size if oldest.exists() else 0
        oldest.unlink(missing_ok=True)
        total_size -= size
        logger.debug("Cache size evict (disk): {} ({}B)", oldest.stem, size)


def _disk_stats() -> dict:
    """Return disk cache statistics."""
    cache_dir = settings.cache_dir
    if not cache_dir.exists():
        return {"files": 0, "size_bytes": 0, "max_files": _MAX_DISK_FILES, "max_size_mb": _MAX_DISK_SIZE_MB}

    files = list(cache_dir.glob("*.pkl"))
    total_size = sum(f.stat().st_size for f in files)
    return {
        "files": len(files),
        "size_bytes": total_size,
        "size_mb": round(total_size / 1024 / 1024, 2),
        "max_files": _MAX_DISK_FILES,
        "max_size_mb": _MAX_DISK_SIZE_MB,
    }


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------


def cached(
    ttl: int,
    *,
    disk: bool = False,
    market_hours_only: bool = False,
    retries: int = 3,
    stale_on_error: bool = True,
):
    """
    Cache decorator with retry, stale-fallback, and LRU eviction.

    Args:
        ttl: Time-to-live in seconds.
        disk: If True, also persist to disk (~/.stk/cache/).
        market_hours_only: If True, extend TTL 10x outside market hours.
        retries: Max attempts on failure (exponential backoff).
        stale_on_error: If True, return expired cache on total failure.
    """
    if retries < 1:
        raise ValueError("retries must be >= 1")

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not _is_cache_enabled():
                return func(*args, **kwargs)

            key = _make_key(func, args, kwargs)
            now = time.time()

            # 1. Check memory cache (LRU)
            entry = _mem_get(key)
            if entry and entry[0] > now:
                logger.debug("Cache HIT (mem): {}", key)
                return entry[1]

            # 2. Check disk cache
            if disk:
                entry = _read_disk(key)
                if entry and entry[0] > now:
                    logger.debug("Cache HIT (disk): {}", key)
                    _mem_set(key, entry[0], entry[1])
                    return entry[1]

            # 3. Call original function with retry
            logger.debug("Cache MISS: {}", key)
            last_err: Exception | None = None
            for attempt in range(retries):
                try:
                    result = func(*args, **kwargs)

                    # Compute effective TTL
                    effective_ttl = ttl
                    if market_hours_only and not _is_market_hours():
                        effective_ttl = ttl * 10

                    expire_ts = time.time() + effective_ttl
                    _mem_set(key, expire_ts, result)
                    if disk:
                        _write_disk(key, expire_ts, result)
                        _evict_disk_if_needed()

                    return result
                except Exception as e:
                    last_err = e
                    if attempt < retries - 1:
                        delay = (2 ** attempt) + random.uniform(-0.5, 0.5)
                        delay = max(0.1, delay)
                        logger.debug(
                            "Retry {}/{} for {} after {:.1f}s: {}",
                            attempt + 1,
                            retries,
                            key,
                            delay,
                            e,
                        )
                        time.sleep(delay)

            # 4. All retries failed → try stale cache
            if stale_on_error:
                stale = _get_stale(key, disk)
                if stale is not None:
                    logger.debug("Cache STALE (fallback): {}", key)
                    return stale

            if last_err is not None:
                raise last_err
            raise RuntimeError("Cache wrapper exhausted retries without capturing an error")

        return wrapper

    return decorator


def _get_stale(key: str, disk: bool) -> Any | None:
    """Return stale (expired) cached value if available, else None."""
    entry = _mem_get(key)
    if entry:
        return entry[1]
    if disk:
        entry = _read_disk(key)
        if entry:
            return entry[1]
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def clear_cache(prefix: str = "") -> int:
    """Clear cache entries matching prefix. Returns count of cleared entries."""
    count = _mem_clear(prefix)

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


def cache_stats() -> dict:
    """Return cache statistics (memory + disk)."""
    mem = _mem_stats()
    disk = _disk_stats()
    return {
        "memory": mem,
        "disk": disk,
        "disabled": not _is_cache_enabled(),
    }
