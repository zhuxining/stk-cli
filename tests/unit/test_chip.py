"""Tests for chip distribution service."""

from decimal import Decimal
from unittest.mock import patch

import pandas as pd
import pytest

from stk.errors import SourceError
from stk.services.chip import get_chip_distribution


@patch("stk.services.chip.ak")
def test_get_chip_distribution(mock_ak):
    """Test chip distribution returns correct model."""
    df = pd.DataFrame([
        {
            "日期": "2026-03-04",
            "获利比例": 0.127578,
            "平均成本": 1441.23,
            "90成本-低": 1352.36,
            "90成本-高": 1549.62,
            "90集中度": 0.067975,
            "70成本-低": 1406.55,
            "70成本-高": 1501.93,
            "70集中度": 0.032794,
        },
        {
            "日期": "2026-03-05",
            "获利比例": 0.123135,
            "平均成本": 1441.23,
            "90成本-低": 1352.36,
            "90成本-高": 1549.62,
            "90集中度": 0.067975,
            "70成本-低": 1406.55,
            "70成本-高": 1501.93,
            "70集中度": 0.032794,
        },
    ])
    mock_ak.stock_cyq_em.return_value = df

    result = get_chip_distribution("600519")
    assert result.symbol == "600519.SH"
    assert result.avg_cost == Decimal("1441.23")
    assert result.profit_ratio == Decimal("0.123135")
    assert result.concentration == Decimal("0.067975")
    assert len(result.chips) == 1
    assert result.chips[0]["date"] == "2026-03-05"


@patch("stk.services.chip.ak")
def test_get_chip_distribution_empty(mock_ak):
    """Test empty chip data raises SourceError."""
    mock_ak.stock_cyq_em.return_value = pd.DataFrame()

    with pytest.raises(SourceError, match="No chip distribution data"):
        get_chip_distribution("600519")
