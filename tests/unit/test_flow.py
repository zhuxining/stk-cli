"""Tests for flow service — stock flow and flow rankings."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from stk.errors import SourceError
from stk.services.flow import get_flow_rank, get_stock_flow


@patch("stk.services.flow.ak")
def test_get_flow_rank_sector(mock_ak):
    """Test sector fund flow ranking."""
    df = pd.DataFrame([
        {"名称": "半导体", "今日涨跌幅": 1.5, "今日主力净流入 - 净额": 500000000},
        {"名称": "白酒", "今日涨跌幅": -0.8, "今日主力净流入 - 净额": -200000000},
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
        {"名称": "人工智能", "今日涨跌幅": 3.0, "今日主力净流入 - 净额": 1e9},
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
        {"代码": "600519", "简称": "贵州茅台", "涨跌幅": 2.0, "主力净流入 - 净额": 1e8},
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


@patch("stk.services.flow.get_longport_ctx")
def test_get_stock_flow(mock_get_longport_ctx):
    """Test individual stock flow via longport capital_distribution."""
    cap_in = MagicMock()
    cap_in.large = Decimal(100)
    cap_in.medium = Decimal(60)
    cap_in.small = Decimal(30)

    cap_out = MagicMock()
    cap_out.large = Decimal(50)
    cap_out.medium = Decimal(40)
    cap_out.small = Decimal(20)

    dist = MagicMock()
    dist.capital_in = cap_in
    dist.capital_out = cap_out
    mock_get_longport_ctx.return_value.capital_distribution.return_value = dist
    mock_get_longport_ctx.return_value.capital_flow.return_value = []

    result = get_stock_flow("600519")
    assert result.symbol == "600519.SH"
    assert result.large_in == Decimal(100)
    assert result.large_out == Decimal(50)
    assert result.medium_in == Decimal(60)
    assert result.small_out == Decimal(20)
