"""Tests for sector/concept quote service."""

from decimal import Decimal
from unittest.mock import patch

import pandas as pd
import pytest

from stk.errors import SourceError
from stk.models.common import TargetType
from stk.services.quote import get_quote


@patch("stk.services.quote.ak")
def test_get_sector_quote(mock_ak):
    """Test sector board quote."""
    df = pd.DataFrame([
        {
            "板块代码": "BK0001",
            "板块名称": "半导体",
            "最新价": 1200.5,
            "涨跌额": 15.3,
            "涨跌幅": 1.29,
            "总市值": 5e12,
        },
        {
            "板块代码": "BK0002",
            "板块名称": "白酒",
            "最新价": 800.0,
            "涨跌额": -5.0,
            "涨跌幅": -0.62,
            "总市值": 3e12,
        },
    ])
    mock_ak.stock_board_industry_name_em.return_value = df

    result = get_quote("半导体", target_type=TargetType.SECTOR)
    assert result.name == "半导体"
    assert result.last == Decimal("1200.5")
    assert result.change_pct == Decimal("1.29")


@patch("stk.services.quote.ak")
def test_get_concept_quote(mock_ak):
    """Test concept board quote."""
    df = pd.DataFrame([
        {
            "板块代码": "BK0100",
            "板块名称": "ChatGPT概念",
            "最新价": 500.0,
            "涨跌幅": 2.5,
            "总市值": 1e12,
        },
    ])
    mock_ak.stock_board_concept_name_em.return_value = df

    result = get_quote("ChatGPT", target_type=TargetType.CONCEPT)
    assert result.name == "ChatGPT概念"
    assert result.last == Decimal("500.0")


@patch("stk.services.quote.ak")
def test_get_sector_quote_not_found(mock_ak):
    """Test sector not found raises SourceError."""
    df = pd.DataFrame([
        {"板块代码": "BK0001", "板块名称": "半导体", "最新价": 100, "涨跌幅": 1.0, "总市值": 1e12}
    ])
    mock_ak.stock_board_industry_name_em.return_value = df

    with pytest.raises(SourceError, match="not found"):
        get_quote("不存在的板块", target_type=TargetType.SECTOR)
