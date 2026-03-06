"""Shared test fixtures."""

import pytest

from stk.config import settings
from stk.deps import get_longport_ctx
from stk.store.cache import _mem_cache


@pytest.fixture(autouse=True)
def _clear_longport_cache():
    """Clear lru_cache between tests to prevent cross-contamination."""
    get_longport_ctx.cache_clear()
    yield
    get_longport_ctx.cache_clear()


@pytest.fixture(autouse=True)
def _clear_api_cache(tmp_path):
    """Clear API response cache and use temp disk dir between tests."""
    _mem_cache.clear()
    original_dir = settings.cache_dir
    settings.cache_dir = tmp_path / "cache"
    yield
    _mem_cache.clear()
    settings.cache_dir = original_dir
