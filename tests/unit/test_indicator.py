"""Tests for indicator calculation service."""

from decimal import Decimal
from unittest.mock import patch

import pytest

from stk.errors import IndicatorError
from stk.models.history import Candlestick
from stk.services.indicator import calc_indicator


def _make_candles(count: int = 30) -> list[Candlestick]:
    """Generate synthetic candlestick data for testing."""
    base = 100.0
    candles = []
    for i in range(count):
        price = base + i * 0.5
        candles.append(
            Candlestick(
                date=f"2025-01-{i + 1:02d}",
                open=Decimal(str(price - 0.2)),
                high=Decimal(str(price + 1.0)),
                low=Decimal(str(price - 1.0)),
                close=Decimal(str(price)),
                volume=1000000 + i * 10000,
                turnover=Decimal(str(price * 1000000)),
            )
        )
    return candles


@patch("stk.services.indicator.get_history")
def test_calc_ma(mock_history):
    mock_history.return_value = _make_candles(30)
    result = calc_indicator("600519", "MA", count=30, timeperiod=5)
    assert result.symbol == "600519"
    assert result.indicator == "MA"
    assert len(result.values) == 30
    # First 4 should be None (not enough data for MA5)
    assert result.values[0]["MA5"] is None
    # 5th value should be computed
    assert result.values[4]["MA5"] is not None


@patch("stk.services.indicator.get_history")
def test_calc_macd(mock_history):
    mock_history.return_value = _make_candles(60)
    result = calc_indicator("600519", "MACD", count=60)
    assert result.indicator == "MACD"
    assert len(result.values) == 60
    # MACD output has three columns
    assert "MACD" in result.values[-1]
    assert "signal" in result.values[-1]
    assert "hist" in result.values[-1]


@patch("stk.services.indicator.get_history")
def test_calc_rsi(mock_history):
    mock_history.return_value = _make_candles(30)
    result = calc_indicator("600519", "RSI", count=30, timeperiod=14)
    assert result.indicator == "RSI"
    assert result.values[-1]["RSI"] is not None


@patch("stk.services.indicator.get_history")
def test_calc_boll(mock_history):
    mock_history.return_value = _make_candles(30)
    result = calc_indicator("600519", "BOLL", count=30)
    assert result.indicator == "BOLL"
    last = result.values[-1]
    assert "upper" in last
    assert "middle" in last
    assert "lower" in last


@patch("stk.services.indicator.get_history")
def test_calc_kdj(mock_history):
    mock_history.return_value = _make_candles(30)
    result = calc_indicator("600519", "KDJ", count=30)
    assert result.indicator == "KDJ"
    last = result.values[-1]
    assert "K" in last
    assert "D" in last
    assert "J" in last


def test_unknown_indicator():
    with pytest.raises(IndicatorError, match="Unknown indicator"):
        calc_indicator("600519", "UNKNOWN")
