"""Tests for the current-state signal assessment."""

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from stk.errors import IndicatorError
from stk.services.score import _closed_daily_df, calc_score


def test_closed_daily_df_drops_current_cn_bar_before_close():
    df = pd.DataFrame({"date": ["2026-05-25 00:00:00", "2026-05-26 00:00:00"]})
    now = datetime(2026, 5, 26, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai"))

    result = _closed_daily_df(df, "600519.SH", now=now)

    assert result["date"].tolist() == ["2026-05-25 00:00:00"]


@patch("stk.services.score._calc_supertrend_arrays")
@patch("stk.services.score.talib.RSI")
@patch("stk.services.score.get_history")
def test_calc_score_returns_buy_assessment(
    mock_history,
    mock_rsi,
    mock_supertrend,
    make_candles,
):
    candles = make_candles(60)
    close = np.array([float(item.close) for item in candles])
    mock_history.return_value = candles
    mock_rsi.return_value = np.full(60, 55.0)
    mock_supertrend.return_value = (
        close - 3,
        np.ones(60, dtype=int),
        np.full(60, 2.0),
    )

    result = calc_score("600519")

    assert result.symbol == "600519.SH"
    assert result.state == "buy"
    assert "healthy_continuation" in result.triggers
    assert result.indicators.max_entry_price is not None
    assert result.risk is not None
    assert result.risk.stop_loss < result.indicators.close
    assert not hasattr(result.risk, "target_1")


@patch("stk.services.score._calc_supertrend_arrays")
@patch("stk.services.score.talib.RSI")
@patch("stk.services.score.get_history")
def test_sell_signal_has_no_short_targets(
    mock_history,
    mock_rsi,
    mock_supertrend,
    make_candles,
):
    candles = make_candles(60)
    close = np.array([float(item.close) for item in candles])
    mock_history.return_value = candles
    mock_rsi.return_value = np.full(60, 55.0)
    mock_supertrend.return_value = (
        close + 3,
        -np.ones(60, dtype=int),
        np.full(60, 2.0),
    )

    result = calc_score("600519")

    assert result.state == "sell"
    assert result.triggers == ["supertrend_bearish"]
    assert result.risk is None


@patch("stk.services.score._calc_supertrend_arrays")
@patch("stk.services.score.talib.RSI")
@patch("stk.services.score.get_history")
def test_overheated_trend_stays_watch(
    mock_history,
    mock_rsi,
    mock_supertrend,
    make_candles,
):
    candles = make_candles(60)
    close = np.array([float(item.close) for item in candles])
    mock_history.return_value = candles
    mock_rsi.return_value = np.full(60, 75.0)
    mock_supertrend.return_value = (
        close - 3,
        np.ones(60, dtype=int),
        np.full(60, 2.0),
    )

    result = calc_score("600519")

    assert result.state == "watch"
    assert result.triggers == []
    assert any("过热" in reason for reason in result.reasons)


@patch("stk.services.score._calc_supertrend_arrays")
@patch("stk.services.score.talib.RSI")
@patch("stk.services.score.get_history")
def test_optional_details_are_attached_without_refetch(
    mock_history,
    mock_rsi,
    mock_supertrend,
    make_candles,
):
    candles = make_candles(60)
    close = np.array([float(item.close) for item in candles])
    mock_history.return_value = candles
    mock_rsi.return_value = np.full(60, 55.0)
    mock_supertrend.return_value = (
        close - 3,
        np.ones(60, dtype=int),
        np.full(60, 2.0),
    )

    result = calc_score("600519", recent_bars=3, include_factors=True)

    assert mock_history.call_count == 1
    assert result.recent_bars is not None
    assert len(result.recent_bars) == 3
    assert result.quality.factors is not None


@patch("stk.services.score.get_history")
def test_score_rejects_insufficient_history(mock_history, make_candles):
    mock_history.return_value = make_candles(20)

    with pytest.raises(IndicatorError, match="Insufficient"):
        calc_score("600519")
