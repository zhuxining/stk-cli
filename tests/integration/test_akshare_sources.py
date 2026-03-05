"""
Integration tests for all akshare API connectivity.

This test file verifies that all akshare APIs used by stk-cli are accessible.
Run with: uv run pytest -m integration tests/integration/test_akshare_sources.py -v
"""

from datetime import UTC, datetime

import akshare as ak
import pytest

pytestmark = pytest.mark.integration


class TestBoardAPIs:
    """Test board service APIs."""

    def test_stock_board_industry_name_em(self):
        """Test industry board list API."""
        df = ak.stock_board_industry_name_em()
        assert not df.empty, "Industry board list should not be empty"
        assert "板块名称" in df.columns
        assert "板块代码" in df.columns

    def test_stock_board_concept_name_em(self):
        """Test concept board list API."""
        df = ak.stock_board_concept_name_em()
        assert not df.empty, "Concept board list should not be empty"
        assert "板块名称" in df.columns

    def test_stock_board_industry_cons_em(self):
        """Test industry board constituents API."""
        df = ak.stock_board_industry_cons_em(symbol="酿酒行业")
        assert not df.empty, "Industry constituents should not be empty"
        assert "代码" in df.columns

    def test_stock_board_concept_cons_em(self):
        """Test concept board constituents API."""
        df = ak.stock_board_concept_cons_em(symbol="人工智能")
        assert not df.empty, "Concept constituents should not be empty"
        assert "代码" in df.columns

    def test_stock_sector_fund_flow_hist(self):
        """Test sector fund flow history API."""
        df = ak.stock_sector_fund_flow_hist(symbol="酿酒行业")
        assert not df.empty, "Sector fund flow history should not be empty"

    def test_stock_concept_fund_flow_hist(self):
        """Test concept fund flow history API."""
        df = ak.stock_concept_fund_flow_hist(symbol="人工智能")
        assert not df.empty, "Concept fund flow history should not be empty"

    def test_stock_sector_fund_flow_summary(self):
        """Test sector fund flow summary API."""
        df = ak.stock_sector_fund_flow_summary(symbol="酿酒行业", indicator="今日")
        assert not df.empty, "Sector fund flow summary should not be empty"


class TestFlowAPIs:
    """Test flow service APIs."""

    def test_stock_individual_fund_flow(self):
        """Test individual stock fund flow API."""
        df = ak.stock_individual_fund_flow(stock="000001", market="sz")
        assert not df.empty, "Individual fund flow should not be empty"

    def test_stock_individual_fund_flow_rank(self):
        """Test individual fund flow rank API."""
        df = ak.stock_individual_fund_flow_rank(indicator="今日")
        assert not df.empty, "Fund flow rank should not be empty"

    def test_stock_main_fund_flow(self):
        """Test main fund flow API."""
        df = ak.stock_main_fund_flow(symbol="沪深A股")
        assert not df.empty, "Main fund flow should not be empty"

    def test_stock_sector_fund_flow_rank(self):
        """Test sector fund flow rank API."""
        df = ak.stock_sector_fund_flow_rank(indicator="今日")
        assert not df.empty, "Sector fund flow rank should not be empty"

    def test_stock_market_fund_flow(self):
        """Test market fund flow API."""
        df = ak.stock_market_fund_flow()
        assert not df.empty, "Market fund flow should not be empty"


class TestMarketAPIs:
    """Test market service APIs."""

    def test_stock_zh_a_spot_em(self):
        """Test A-share spot quotes API."""
        df = ak.stock_zh_a_spot_em()
        assert not df.empty, "A-share spot quotes should not be empty"

    def test_stock_zt_pool_em(self):
        """Test limit-up pool API."""
        today = datetime.now(UTC).strftime("%Y%m%d")
        df = ak.stock_zt_pool_em(date=today)
        # May be empty if no limit-up stocks today
        assert df is not None, "Limit-up pool API should return a result"

    def test_stock_zt_pool_dtgc_em(self):
        """Test limit-up pool (day-to-day cover) API."""
        today = datetime.now(UTC).strftime("%Y%m%d")
        df = ak.stock_zt_pool_dtgc_em(date=today)
        # May be empty if no matching stocks today
        assert df is not None, "DTGC pool API should return a result"


class TestNewsAPIs:
    """Test news service APIs."""

    def test_stock_news_em(self):
        """Test stock news API."""
        df = ak.stock_news_em(symbol="000001")
        assert not df.empty, "Stock news should not be empty"


class TestRankAPIs:
    """Test rank service APIs."""

    def test_stock_hot_rank_em(self):
        """Test hot stock rank API."""
        df = ak.stock_hot_rank_em()
        assert not df.empty, "Hot stock rank should not be empty"


class TestChipAPIs:
    """Test chip service APIs."""

    def test_stock_cyq_em(self):
        """Test chip distribution API."""
        df = ak.stock_cyq_em(symbol="600519", adjust="")
        assert not df.empty, "Chip distribution should not be empty"


class TestFundamentalAPIs:
    """Test fundamental service APIs."""

    def test_stock_zyjs_ths(self):
        """Test main operations summary API."""
        df = ak.stock_zyjs_ths(symbol="600519")
        assert not df.empty, "Main operations summary should not be empty"
