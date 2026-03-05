"""Tests for money flow service."""

from decimal import Decimal
from unittest.mock import patch

import pandas as pd
import pytest

from stk.errors import SourceError
from stk.services.flow import (
    get_flow_rank,
    get_sector_flow_detail,
    get_sector_flow_hist,
)


@patch("stk.services.flow.ak")
def test_get_flow_rank_sector(mock_ak):
    """Test sector fund flow ranking."""
    df = pd.DataFrame([
        {"名称": "半导体", "今日涨跌幅": 1.5, "今日主力净流入-净额": 500000000},
        {"名称": "白酒", "今日涨跌幅": -0.8, "今日主力净流入-净额": -200000000},
    ])
    mock_ak.stock_sector_fund_flow_rank.return_value = df

    result = get_flow_rank(scope="sector", period="今日")
    assert result.scope == "sector"
    assert len(result.items) == 2
    assert result.items[0].name == "半导体"
    mock_ak.stock_sector_fund_flow_rank.assert_called_with(
        indicator="今日",
        sector_type="行业资金流",
    )


@patch("stk.services.flow.ak")
def test_get_flow_rank_concept(mock_ak):
    """Test concept fund flow ranking."""
    df = pd.DataFrame([
        {"名称": "人工智能", "今日涨跌幅": 3.0, "今日主力净流入-净额": 1e9},
    ])
    mock_ak.stock_sector_fund_flow_rank.return_value = df

    result = get_flow_rank(scope="concept", period="今日")
    assert result.items[0].name == "人工智能"
    mock_ak.stock_sector_fund_flow_rank.assert_called_with(
        indicator="今日",
        sector_type="概念资金流",
    )


@patch("stk.services.flow.ak")
def test_get_flow_rank_stock(mock_ak):
    """Test individual stock fund flow ranking."""
    df = pd.DataFrame([
        {"代码": "600519", "简称": "贵州茅台", "涨跌幅": 2.0, "主力净流入-净额": 1e8},
    ])
    mock_ak.stock_individual_fund_flow_rank.return_value = df

    result = get_flow_rank(scope="stock", period="今日")
    assert result.items[0].code == "600519"
    assert result.items[0].name == "贵州茅台"


@patch("stk.services.flow.ak")
def test_get_flow_rank_empty(mock_ak):
    """Test empty ranking raises SourceError."""
    mock_ak.stock_individual_fund_flow_rank.return_value = pd.DataFrame()

    with pytest.raises(SourceError, match="No stock flow rank"):
        get_flow_rank(scope="stock")


def test_get_flow_rank_unknown_scope():
    """Test unknown scope raises SourceError."""
    with pytest.raises(SourceError, match="Unknown scope"):
        get_flow_rank(scope="invalid")


@patch("stk.services.flow.ak")
def test_get_sector_flow_hist(mock_ak):
    """Test sector historical fund flow."""
    df = pd.DataFrame([
        {"日期": "2025-03-01", "主力净流入-净额": 1e8, "涨跌幅": 1.2},
        {"日期": "2025-03-02", "主力净流入-净额": -5e7, "涨跌幅": -0.5},
    ])
    mock_ak.stock_sector_fund_flow_hist.return_value = df

    result = get_sector_flow_hist("酿酒行业", type="sector")
    assert result.name == "酿酒行业"
    assert result.type == "sector"
    assert len(result.days) == 2
    assert result.days[0].date == "2025-03-01"


@patch("stk.services.flow.ak")
def test_get_sector_flow_detail(mock_ak):
    """Test sector individual stocks detail."""
    df = pd.DataFrame([
        {"代码": "600519", "简称": "贵州茅台", "主力净流入-净额": 1e8},
    ])
    mock_ak.stock_sector_fund_flow_summary.return_value = df

    result = get_sector_flow_detail("酿酒行业", period="今日")
    assert result.sector == "酿酒行业"
    assert result.items[0].code == "600519"


@patch("stk.services.flow.ak")
def test_get_sector_flow_detail_empty(mock_ak):
    """Test empty sector detail raises SourceError."""
    mock_ak.stock_sector_fund_flow_summary.return_value = pd.DataFrame()

    with pytest.raises(SourceError, match="No detail"):
        get_sector_flow_detail("不存在")
