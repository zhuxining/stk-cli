"""Tests for indicator calculation service."""

from unittest.mock import patch

import pytest

from stk.errors import IndicatorError
from stk.services.indicator import calc_all_indicators, calc_indicator, get_daily


@patch("stk.services.indicator.get_history")
def test_calc_ema_multi_period(mock_history, make_candles):
    """Test EMA indicator with multiple periods (5/10/20/60)."""
    mock_history.return_value = make_candles(80)
    result = calc_indicator("600519", "EMA", count=80)
    assert result.symbol == "600519"
    assert result.indicator == "EMA"
    assert len(result.values) == 80
    # Newest first: first row should have all four EMA columns
    newest = result.values[0]
    assert "EMA5" in newest
    assert "EMA10" in newest
    assert "EMA20" in newest
    assert "EMA60" in newest
    assert newest["EMA5"] is not None


@patch("stk.services.indicator.get_history")
def test_calc_macd(mock_history, make_candles):
    """Test MACD indicator calculation."""
    mock_history.return_value = make_candles(60)
    result = calc_indicator("600519", "MACD", count=60)
    assert result.indicator == "MACD"
    assert len(result.values) == 60
    # Newest first: first row has three columns
    assert "MACD" in result.values[0]
    assert "signal" in result.values[0]
    assert "hist" in result.values[0]


@patch("stk.services.indicator.get_history")
def test_calc_rsi(mock_history, make_candles):
    """Test RSI indicator calculation."""
    mock_history.return_value = make_candles(30)
    result = calc_indicator("600519", "RSI", count=30, timeperiod=14)
    assert result.indicator == "RSI"
    assert result.values[0]["RSI"] is not None


@patch("stk.services.indicator.get_history")
def test_calc_boll(mock_history, make_candles):
    """Test Bollinger Bands calculation."""
    mock_history.return_value = make_candles(30)
    result = calc_indicator("600519", "BOLL", count=30)
    assert result.indicator == "BOLL"
    newest = result.values[0]
    assert "upper" in newest
    assert "middle" in newest
    assert "lower" in newest


@patch("stk.services.indicator.get_history")
def test_calc_kdj(mock_history, make_candles):
    """Test KDJ indicator calculation."""
    mock_history.return_value = make_candles(30)
    result = calc_indicator("600519", "KDJ", count=30)
    assert result.indicator == "KDJ"
    newest = result.values[0]
    assert "K" in newest
    assert "D" in newest
    assert "J" in newest


@patch("stk.services.indicator.get_history")
def test_calc_all_indicators(mock_history, make_candles):
    """Test calculating all indicators in one pass, returning only last N rows."""
    mock_history.return_value = make_candles(70)  # 10 + 60 warmup
    result = calc_all_indicators("600519", count=10)
    assert result.symbol == "600519"
    assert set(result.indicators.keys()) == {"EMA", "MACD", "RSI", "KDJ", "BOLL", "ATR"}
    # History fetched only once
    mock_history.assert_called_once()
    # Each indicator returns exactly count rows
    for values in result.indicators.values():
        assert len(values) == 10


@patch("stk.services.indicator.get_history")
def test_get_daily(mock_history, make_candles):
    """Test get_daily merges OHLCV + all indicators per day."""
    mock_history.return_value = make_candles(70)  # 10 + 60 warmup
    result = get_daily("600519", count=10)
    assert result.symbol == "600519"
    assert len(result.days) == 10
    mock_history.assert_called_once()

    newest = result.days[0]
    # OHLCV fields
    for field in ("date", "open", "high", "low", "close", "volume"):
        assert field in newest
    # Change percent
    assert "change_pct" in newest
    # Indicator fields
    assert "EMA5" in newest
    assert "EMA60" in newest
    assert "MACD" in newest
    assert "RSI" in newest
    assert "K" in newest
    assert "upper" in newest
    assert "ATR14" in newest


def test_unknown_indicator():
    """Test error for unknown indicator."""
    with pytest.raises(IndicatorError, match="Unknown indicator"):
        calc_indicator("600519", "UNKNOWN")
