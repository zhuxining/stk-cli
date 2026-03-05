"""Tests for fundamental service (akshare-based: industry comparison)."""

from decimal import Decimal
from unittest.mock import patch

import pandas as pd
import pytest

from stk.errors import SourceError
from stk.services.fundamental import get_comparison


def _make_comparison_df(columns: list[str], rows: list[list]) -> pd.DataFrame:
    """Build a synthetic comparison DataFrame."""
    return pd.DataFrame(rows, columns=columns)


@patch("stk.services.fundamental.ak")
def test_get_comparison_growth(mock_ak):
    """Test growth comparison returns correct structure."""
    df = _make_comparison_df(
        ["排名", "代码", "简称", "EPS(TTM)", "营收同比增长率"],
        [
            ["-", "-", "行业中值", "1.50", "8.20"],
            ["-", "-", "行业平均", "2.10", "10.50"],
            ["1", "600519", "贵州茅台", "5.80", "15.30"],
            ["2", "000858", "五粮液", "3.20", "12.10"],
        ],
    )
    mock_ak.stock_zh_growth_comparison_em.return_value = df

    result = get_comparison("600519", category="growth")
    assert result.symbol == "600519.SH"
    assert result.category == "growth"
    assert len(result.companies) == 4
    # Industry median
    assert result.companies[0].name == "行业中值"
    assert result.companies[0].metrics["EPS(TTM)"] == Decimal("1.50")
    # Target stock
    assert result.companies[2].code == "600519"
    assert result.companies[2].metrics["营收同比增长率"] == Decimal("15.30")


@patch("stk.services.fundamental.ak")
def test_get_comparison_valuation(mock_ak):
    """Test valuation comparison."""
    df = _make_comparison_df(
        ["排名", "代码", "简称", "PE-TTM", "PB", "PEG"],
        [
            ["-", "-", "行业中值", "25.00", "3.50", "1.20"],
            ["-", "-", "行业平均", "30.00", "4.00", "1.50"],
            ["1", "600519", "贵州茅台", "19.00", "8.50", "0.80"],
        ],
    )
    mock_ak.stock_zh_valuation_comparison_em.return_value = df

    result = get_comparison("600519", category="valuation")
    assert result.category == "valuation"
    assert result.companies[2].metrics["PE-TTM"] == Decimal("19.00")
    assert result.companies[2].metrics["PEG"] == Decimal("0.80")


@patch("stk.services.fundamental.ak")
def test_get_comparison_dupont(mock_ak):
    """Test DuPont comparison."""
    df = _make_comparison_df(
        ["排名", "代码", "简称", "ROE", "净利率", "资产周转率", "权益乘数"],
        [
            ["-", "-", "行业中值", "10.00", "15.00", "0.50", "1.50"],
            ["-", "-", "行业平均", "12.00", "18.00", "0.55", "1.60"],
            ["1", "600519", "贵州茅台", "30.00", "50.00", "0.40", "1.20"],
        ],
    )
    mock_ak.stock_zh_dupont_comparison_em.return_value = df

    result = get_comparison("600519", category="dupont")
    assert result.category == "dupont"
    assert result.companies[2].metrics["ROE"] == Decimal("30.00")
    assert result.companies[2].metrics["净利率"] == Decimal("50.00")


@patch("stk.services.fundamental.ak")
def test_get_comparison_empty(mock_ak):
    """Test empty DataFrame raises SourceError."""
    mock_ak.stock_zh_growth_comparison_em.return_value = pd.DataFrame()

    with pytest.raises(SourceError, match="No growth comparison data"):
        get_comparison("600519", category="growth")


def test_get_comparison_bad_category():
    """Test unknown category."""
    with pytest.raises(SourceError, match="Unknown category"):
        get_comparison("600519", category="unknown")


@patch("stk.services.fundamental.ak")
def test_get_comparison_nan_handling(mock_ak):
    """Test NaN/dash values become None in metrics."""
    df = _make_comparison_df(
        ["排名", "代码", "简称", "EPS(TTM)", "营收同比增长率"],
        [
            ["-", "-", "行业中值", "NaN", "-"],
            ["1", "600519", "贵州茅台", "5.80", "nan"],
        ],
    )
    mock_ak.stock_zh_growth_comparison_em.return_value = df

    result = get_comparison("600519", category="growth")
    assert result.companies[0].metrics["EPS(TTM)"] is None
    assert result.companies[0].metrics["营收同比增长率"] is None
    assert result.companies[1].metrics["营收同比增长率"] is None
