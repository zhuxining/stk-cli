"""Shared test fixtures."""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from stk.config import settings
from stk.deps import get_longport_ctx
from stk.models.history import Candlestick
from stk.store.cache import _mem_cache


@pytest.fixture(autouse=True)
def _clear_longport_cache():
    """Clear lru_cache between tests to prevent cross-contamination."""
    get_longport_ctx.cache_clear()
    yield
    get_longport_ctx.cache_clear()


@pytest.fixture(autouse=True)
def _clear_api_cache(tmp_path, monkeypatch):
    """Clear API response cache and use temp disk dir between tests."""
    _mem_cache.clear()
    monkeypatch.setattr(settings, "cache_dir", tmp_path / "cache")
    yield
    _mem_cache.clear()


@pytest.fixture
def make_candles():
    """Factory fixture to generate synthetic candlestick data."""

    def _make(count: int = 60) -> list[Candlestick]:
        base = 100.0
        candles = []
        for i in range(count):
            price = base + i * 0.5
            candles.append(
                Candlestick(
                    date=(datetime(2024, 1, 1) + timedelta(days=i)).strftime("%Y-%m-%d"),
                    open=Decimal(str(price - 0.2)),
                    high=Decimal(str(price + 1.0)),
                    low=Decimal(str(price - 1.0)),
                    close=Decimal(str(price)),
                    volume=1000000 + i * 10000,
                    turnover=Decimal(str(price * 1000000)),
                )
            )
        return candles

    return _make
