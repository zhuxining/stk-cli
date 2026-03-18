"""Tests for board service — sector/concept board data and money flow."""

from decimal import Decimal
from unittest.mock import patch

import pandas as pd
import pytest

from stk.errors import SourceError
from stk.services.board import (
    get_board_cons,
    get_board_list,
    get_sector_flow_detail,
    get_sector_flow_hist,
)


@patch("stk.services.board.ak")
def test_get_board_list_sector(mock_ak):
    """Test sector board list."""
    df = pd.DataFrame([
        {"板块名称": "酿酒行业", "板块代码": "BK001", "最新价": Decimal(1000)},
        {"板块名称": "半导体", "板块代码": "BK002", "最新价": Decimal(2000)},
    ])
    mock_ak.stock_board_industry_name_em.return_value = df

    result = get_board_list(type="sector")
    assert result.type == "sector"
    assert len(result.items) == 2
    assert result.items[0].name == "酿酒行业"
    mock_ak.stock_board_industry_name_em.assert_called_once()


@patch("stk.services.board.ak")
def test_get_board_list_concept(mock_ak):
    """Test concept board list."""
    df = pd.DataFrame([
        {"板块名称": "人工智能", "板块代码": "BK003", "最新价": Decimal(500)},
    ])
    mock_ak.stock_board_concept_name_em.return_value = df

    result = get_board_list(type="concept")
    assert result.type == "concept"
    mock_ak.stock_board_concept_name_em.assert_called_once()


@patch("stk.services.board.ak")
def test_get_board_list_empty(mock_ak):
    """Test empty board list raises SourceError."""
    mock_ak.stock_board_industry_name_em.return_value = pd.DataFrame()

    with pytest.raises(SourceError, match="No sector board"):
        get_board_list(type="sector")


def test_get_board_list_unknown_type():
    """Test unknown board type raises SourceError."""
    with pytest.raises(SourceError, match="Unknown board type"):
        get_board_list(type="unknown")


@patch("stk.services.board.ak")
def test_get_board_cons(mock_ak):
    """Test board constituents."""
    df = pd.DataFrame([
        {"代码": "600519", "名称": "贵州茅台", "最新价": Decimal(1500)},
        {"代码": "000858", "名称": "五粮液", "最新价": Decimal(100)},
    ])
    mock_ak.stock_board_industry_cons_em.return_value = df

    result = get_board_cons("酿酒行业", type="sector")
    assert result.board == "酿酒行业"
    assert result.type == "sector"
    assert len(result.items) == 2
    assert result.items[0].code == "600519"
    mock_ak.stock_board_industry_cons_em.assert_called_with(symbol="酿酒行业")


@patch("stk.services.board.ak")
def test_get_board_cons_empty(mock_ak):
    """Test empty constituents raises SourceError."""
    mock_ak.stock_board_industry_cons_em.return_value = pd.DataFrame()

    with pytest.raises(SourceError, match="No constituents"):
        get_board_cons("不存在")


@patch("stk.services.board.ak")
def test_get_sector_flow_hist(mock_ak):
    """Test sector historical fund flow."""
    df = pd.DataFrame([
        {"日期": "2025-03-01", "主力净流入 - 净额": Decimal("1e8"), "涨跌幅": Decimal("1.2")},
        {"日期": "2025-03-02", "主力净流入 - 净额": Decimal("-5e7"), "涨跌幅": Decimal("-0.5")},
    ])
    mock_ak.stock_sector_fund_flow_hist.return_value = df

    result = get_sector_flow_hist("酿酒行业", type="sector")
    assert result.name == "酿酒行业"
    assert result.type == "sector"
    assert len(result.days) == 2
    assert result.days[0].date == "2025-03-02"  # newest first


@patch("stk.services.board.ak")
def test_get_sector_flow_hist_empty(mock_ak):
    """Test empty sector flow history raises SourceError."""
    mock_ak.stock_sector_fund_flow_hist.return_value = pd.DataFrame()

    with pytest.raises(SourceError, match="No history flow"):
        get_sector_flow_hist("不存在")


@patch("stk.services.board.ak")
def test_get_sector_flow_detail(mock_ak):
    """Test sector individual stocks detail."""
    df = pd.DataFrame([
        {"代码": "600519", "简称": "贵州茅台", "主力净流入 - 净额": Decimal("1e8")},
    ])
    mock_ak.stock_sector_fund_flow_summary.return_value = df

    result = get_sector_flow_detail("酿酒行业", period="今日")
    assert result.sector == "酿酒行业"
    assert result.items[0].code == "600519"


@patch("stk.services.board.ak")
def test_get_sector_flow_detail_empty(mock_ak):
    """Test empty sector detail raises SourceError."""
    mock_ak.stock_sector_fund_flow_summary.return_value = pd.DataFrame()

    with pytest.raises(SourceError, match="No detail"):
        get_sector_flow_detail("不存在")
