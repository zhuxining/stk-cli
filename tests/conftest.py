"""Shared test fixtures."""

import pytest

from stk.deps import get_longport_ctx


@pytest.fixture(autouse=True)
def _clear_longport_cache():
    """Clear lru_cache between tests to prevent cross-contamination."""
    get_longport_ctx.cache_clear()
    yield
    get_longport_ctx.cache_clear()
