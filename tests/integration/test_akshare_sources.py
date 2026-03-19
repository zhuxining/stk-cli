"""
Integration tests for all akshare API connectivity.

This test file verifies that all akshare APIs used by stk-cli are accessible.
Run with: uv run pytest -m integration tests/integration/test_akshare_sources.py -v
"""

import akshare as ak
import pytest

pytestmark = pytest.mark.integration


class TestFundamentalAPIs:
    """Test fundamental service APIs."""

    def test_stock_zyjs_ths(self):
        """Test main operations summary API."""
        df = ak.stock_zyjs_ths(symbol="600519")
        assert not df.empty, "Main operations summary should not be empty"
