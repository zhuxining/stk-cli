"""Tests for indicator calculation service."""

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pandas as pd

from stk.services.history import candles_to_df
from stk.services.indicator import (
    _calc_supertrend_arrays,
    _to_stock_frame,
    get_daily,
)


@patch("stk.services.indicator.get_history")
def test_get_daily(mock_history, make_candles):
    """Test get_daily merges OHLCV + all indicators per day."""
    mock_history.return_value = make_candles(60)  # 10 + 50 warmup
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
    assert "EMA9" in newest
    assert "EMA26" in newest
    assert "EMA60" in newest
    assert "MACD" in newest
    assert "RSI" in newest
    assert "K" in newest
    assert "upper" in newest
    assert "ATR10" in newest
    assert "ATR14" in newest
    assert "WR" in newest
    assert "Supertrend" in newest
    assert "SupertrendDirection" in newest
    assert newest["ATR10"] is not None
    assert newest["ATR14"] is not None
    assert newest["K"] == 83.3333
    assert newest["D"] == 83.3333
    assert newest["J"] == 83.3333
    assert newest["WR"] == -11.7647
    assert newest["Supertrend"] is not None
    assert newest["SupertrendDirection"] == "bullish"


def test_stockstats_does_not_mutate_input(make_candles):
    """Wrapping and calculating indicators must leave the source frame unchanged."""
    df = candles_to_df(make_candles(60))
    original = df.copy(deep=True)

    stock = _to_stock_frame(df)
    supertrend, direction, atr = _calc_supertrend_arrays(stock)

    pd.testing.assert_frame_equal(df, original)
    assert len(supertrend) == len(df)
    assert direction[-1] == 1
    assert atr[-1] > 0


def test_stockstats_supertrend_is_deterministic_across_threads(make_candles):
    """Concurrent scans share fixed Supertrend settings without result drift."""
    df = candles_to_df(make_candles(60))

    def calculate() -> tuple[float, int, float]:
        stock = _to_stock_frame(df)
        supertrend, direction, atr = _calc_supertrend_arrays(stock)
        return round(supertrend[-1], 8), int(direction[-1]), round(atr[-1], 8)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: calculate(), range(32)))

    assert len(set(results)) == 1
