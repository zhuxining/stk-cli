"""Tests for indicator calculation service."""

from unittest.mock import patch

from stk.services.indicator import get_daily


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
