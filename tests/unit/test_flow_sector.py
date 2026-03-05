"""Tests for sector/concept money flow service."""

from decimal import Decimal
from unittest.mock import patch

import pandas as pd
import pytest

from stk.errors import SourceError
from stk.models.common import TargetType
from stk.services.flow import get_flow


@patch("stk.services.flow.ak")
def test_get_sector_flow(mock_ak):
    """Test sector money flow."""
    df = pd.DataFrame([
        {"名称": "半导体", "今日涨跌幅": 1.5, "今日主力净流入-净额": 500000000},
        {"名称": "白酒", "今日涨跌幅": -0.8, "今日主力净流入-净额": -200000000},
    ])
    mock_ak.stock_sector_fund_flow_rank.return_value = df

    result = get_flow("半导体", target_type=TargetType.SECTOR)
    assert result.sector == "半导体"
    assert result.change_pct == Decimal("1.5")
    assert result.main_net == Decimal(500000000)


@patch("stk.services.flow.ak")
def test_get_concept_flow(mock_ak):
    """Test concept money flow."""
    df = pd.DataFrame([{"名称": "人工智能", "今日涨跌幅": 3.0, "今日主力净流入-净额": 1000000000}])
    mock_ak.stock_sector_fund_flow_rank.return_value = df

    result = get_flow("人工智能", target_type=TargetType.CONCEPT)
    assert result.sector == "人工智能"
    assert result.main_net == Decimal(1000000000)
    mock_ak.stock_sector_fund_flow_rank.assert_called_with(
        indicator="今日", sector_type="概念资金流"
    )


@patch("stk.services.flow.ak")
def test_get_sector_flow_not_found(mock_ak):
    """Test sector not found raises SourceError."""
    df = pd.DataFrame([{"名称": "半导体", "今日涨跌幅": 1.0, "今日主力净流入-净额": 100}])
    mock_ak.stock_sector_fund_flow_rank.return_value = df

    with pytest.raises(SourceError, match="not found"):
        get_flow("不存在的板块", target_type=TargetType.SECTOR)
