"""Tests for the cache decorator."""

import time
from unittest.mock import patch

import pytest

from stk.store.cache import _make_key, _mem_cache, cached, clear_cache


def test_basic_caching():
    """Cached function should return memoized result on second call."""
    call_count = 0

    @cached(ttl=60)
    def add(a, b):
        nonlocal call_count
        call_count += 1
        return a + b

    assert add(1, 2) == 3
    assert add(1, 2) == 3
    assert call_count == 1  # only called once


def test_different_args_different_keys():
    """Different arguments should produce different cache entries."""
    call_count = 0

    @cached(ttl=60)
    def square(n):
        nonlocal call_count
        call_count += 1
        return n * n

    assert square(3) == 9
    assert square(4) == 16
    assert call_count == 2


def test_ttl_expiration():
    """Cache should expire after TTL."""
    call_count = 0

    @cached(ttl=1)
    def greet():
        nonlocal call_count
        call_count += 1
        return "hello"

    assert greet() == "hello"
    assert call_count == 1

    time.sleep(1.1)
    assert greet() == "hello"
    assert call_count == 2  # called again after expiry


def test_cache_key_uniqueness():
    """Keys for different functions/args should be unique."""

    def func_a(x):
        return x

    def func_b(x):
        return x

    key_a1 = _make_key(func_a, (1,), {})
    key_a2 = _make_key(func_a, (2,), {})
    key_b1 = _make_key(func_b, (1,), {})

    assert key_a1 != key_a2
    assert key_a1 != key_b1


def test_kwargs_in_key():
    """Keyword arguments should be part of the cache key."""
    call_count = 0

    @cached(ttl=60)
    def fetch(symbol, *, category="growth"):
        nonlocal call_count
        call_count += 1
        return f"{symbol}:{category}"

    assert fetch("600519", category="growth") == "600519:growth"
    assert fetch("600519", category="valuation") == "600519:valuation"
    assert call_count == 2

    # same call again should be cached
    assert fetch("600519", category="growth") == "600519:growth"
    assert call_count == 2


def test_disk_cache(tmp_path):
    """Disk cache should persist and restore."""
    with patch("stk.store.cache.settings") as mock_settings:
        mock_settings.cache_enabled = True
        mock_settings.cache_dir = tmp_path

        call_count = 0

        @cached(ttl=60, disk=True)
        def compute(x):
            nonlocal call_count
            call_count += 1
            return x * 10

        # First call: miss
        assert compute(5) == 50
        assert call_count == 1

        # Clear memory cache to test disk recovery
        _mem_cache.clear()

        # Second call: should recover from disk
        assert compute(5) == 50
        assert call_count == 1  # not called again

        # Verify disk file exists
        pkl_files = list(tmp_path.glob("*.pkl"))
        assert len(pkl_files) == 1


def test_market_hours_extends_ttl():
    """TTL should be extended 10x outside market hours."""
    call_count = 0

    @cached(ttl=10, market_hours_only=True)
    def data():
        nonlocal call_count
        call_count += 1
        return "market_data"

    with patch("stk.store.cache._is_market_hours", return_value=False):
        assert data() == "market_data"
        assert call_count == 1

        # Check the TTL was extended (10 * 10 = 100s)
        key = next(iter(_mem_cache.keys()))
        expire_ts = _mem_cache[key][0]
        remaining = expire_ts - time.time()
        assert remaining > 50  # well above the base 10s


def test_clear_cache_all():
    """clear_cache() should remove all entries."""

    @cached(ttl=60)
    def f(x):
        return x

    f(1)
    f(2)
    assert len(_mem_cache) == 2

    count = clear_cache()
    assert count >= 2
    assert len(_mem_cache) == 0


def test_clear_cache_with_prefix():
    """clear_cache(prefix) should only remove matching entries."""
    _mem_cache["stk.services.board.get_board_list:abc123"] = (time.time() + 60, "data1")
    _mem_cache["stk.services.rank.get_tech_rank:def456"] = (time.time() + 60, "data2")

    count = clear_cache("stk.services.board")
    assert count == 1
    assert "stk.services.rank.get_tech_rank:def456" in _mem_cache
    assert "stk.services.board.get_board_list:abc123" not in _mem_cache


def test_cache_disabled():
    """When cache_enabled=False, decorator should pass through."""
    call_count = 0

    @cached(ttl=60)
    def f():
        nonlocal call_count
        call_count += 1
        return "result"

    with patch("stk.store.cache.settings") as mock_settings:
        mock_settings.cache_enabled = False
        assert f() == "result"
        assert f() == "result"
        assert call_count == 2  # no caching


def test_exception_not_cached():
    """Exceptions from the wrapped function should not be cached."""
    call_count = 0

    @cached(ttl=60, retries=1)
    def failing():
        nonlocal call_count
        call_count += 1
        raise ValueError("boom")

    with pytest.raises(ValueError):
        failing()
    with pytest.raises(ValueError):
        failing()
    assert call_count == 2  # retried, not cached


def test_retry_on_failure():
    """Cached function should retry on failure with exponential backoff."""
    call_count = 0

    @cached(ttl=60, retries=3)
    def flaky():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("transient")
        return "ok"

    with patch("stk.store.cache.time.sleep"):
        result = flaky()
    assert result == "ok"
    assert call_count == 3


def test_stale_on_error():
    """When all retries fail, return stale cached data if available."""
    call_count = 0

    @cached(ttl=1, retries=1)
    def unstable():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "fresh"
        raise ValueError("down")

    result1 = unstable()
    assert result1 == "fresh"

    # Expire the cache
    time.sleep(1.1)

    # Second call fails but should return stale data
    result2 = unstable()
    assert result2 == "fresh"
    assert call_count == 2


def test_stale_on_error_disabled():
    """When stale_on_error=False, raise on failure even if stale data exists."""
    call_count = 0

    @cached(ttl=1, retries=1, stale_on_error=False)
    def unstable():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "fresh"
        raise ValueError("down")

    unstable()
    time.sleep(1.1)

    with pytest.raises(ValueError):
        unstable()
