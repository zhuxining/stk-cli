"""Tests for the current-state signal assessment."""

from datetime import datetime
from decimal import Decimal
from unittest.mock import patch
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from stk.errors import IndicatorError
from stk.services.score import (
    _closed_daily_df,
    _confirmed_reversal,
    _reversal_triggers,
    calc_score,
)


def _mock_ema(monkeypatch, fast: np.ndarray, slow: np.ndarray) -> None:
    def fake_ema(values, *, timeperiod):
        if timeperiod == 9:
            return fast
        if timeperiod == 26:
            return slow
        return np.asarray(values, dtype=float)

    monkeypatch.setattr("stk.services.score.talib.EMA", fake_ema)


def test_closed_daily_df_drops_current_cn_bar_before_close():
    df = pd.DataFrame({"date": ["2026-05-25 00:00:00", "2026-05-26 00:00:00"]})
    now = datetime(2026, 5, 26, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai"))

    result = _closed_daily_df(df, "600519.SH", now=now)

    assert result["date"].tolist() == ["2026-05-25 00:00:00"]


@pytest.mark.parametrize(
    ("bullish", "expected_code"),
    [
        (True, "ema_bullish_crossover"),
        (False, "ema_bearish_crossover"),
    ],
)
@pytest.mark.parametrize("age", [0, 1, 2, 3])
def test_ema_crosses_are_structured_reversal_events(
    bullish,
    expected_code,
    age,
):
    length = 6
    cross_index = length - 1 - age
    slow = np.full(length, 10.0)
    fast = np.full(length, 9.0 if bullish else 11.0)
    fast[cross_index:] = 11.0 if bullish else 9.0
    df = pd.DataFrame({"date": [f"d{index}" for index in range(length)]})
    direction = np.full(length, 1 if bullish else -1, dtype=int)

    result = _reversal_triggers(
        df,
        ema9=fast,
        ema26=slow,
        direction=direction,
        bullish=bullish,
    )

    if age == 3:
        assert result == []
        return
    assert len(result) == 1
    assert result[0].code == expected_code
    assert result[0].occurred_at == f"d{cross_index}"
    assert result[0].age_bars == age


@pytest.mark.parametrize(
    ("confirmation_age", "expected"),
    [(0, True), (1, True), (2, True), (3, False)],
)
def test_paired_reversal_is_valid_for_three_bars_after_second_event(
    confirmation_age,
    expected,
):
    length = 10
    confirmation_index = length - 1 - confirmation_age
    supertrend_index = confirmation_index - 2
    slow = np.full(length, 10.0)
    fast = np.full(length, 9.0)
    fast[confirmation_index:] = 11.0
    direction = -np.ones(length, dtype=int)
    direction[supertrend_index:] = 1
    df = pd.DataFrame({"date": [f"d{index}" for index in range(length)]})

    result = _confirmed_reversal(
        df,
        ema9=fast,
        ema26=slow,
        direction=direction,
        bullish=True,
    )

    if not expected:
        assert result is None
        return
    assert result is not None
    confirmation, triggers = result
    assert confirmation.confirmed_at == f"d{confirmation_index}"
    assert confirmation.age_bars == confirmation_age
    assert [trigger.code for trigger in triggers] == [
        "supertrend_bullish_reversal",
        "ema_bullish_crossover",
    ]


@pytest.mark.parametrize(
    ("age", "expected_state"),
    [(0, "buy"), (1, "buy"), (2, "buy"), (3, "ignored")],
)
@patch("stk.services.score._calc_supertrend_arrays")
@patch("stk.services.score.talib.RSI")
@patch("stk.services.score.get_history")
def test_bullish_reversal_is_valid_for_three_confirmed_bars(
    mock_history,
    mock_rsi,
    mock_supertrend,
    make_candles,
    monkeypatch,
    age,
    expected_state,
):
    candles = make_candles(60)
    close = np.array([float(item.close) for item in candles])
    direction = np.ones(60, dtype=int)
    flip_index = len(direction) - 1 - age
    direction[:flip_index] = -1
    ema26 = np.full(60, 127.0)
    ema9 = np.full(60, 126.0)
    ema9[flip_index:] = 128.0
    _mock_ema(monkeypatch, ema9, ema26)
    mock_history.return_value = candles
    mock_rsi.return_value = np.full(60, 55.0)
    mock_supertrend.return_value = (
        close - 3,
        direction,
        np.full(60, 2.0),
    )

    result = calc_score("600519")

    assert result.symbol == "600519.SH"
    assert result.state == expected_state
    if expected_state == "buy":
        assert result.triggers[0].code == "supertrend_bullish_reversal"
        assert result.triggers[0].age_bars == age
        assert result.risk is not None
        assert result.risk.stop_loss < result.indicators.close
    else:
        assert result.triggers == []
        assert result.risk is None


@patch("stk.services.score._calc_supertrend_arrays")
@patch("stk.services.score.talib.RSI")
@patch("stk.services.score.get_history")
def test_sell_signal_has_no_short_targets(
    mock_history,
    mock_rsi,
    mock_supertrend,
    make_candles,
    monkeypatch,
):
    candles = make_candles(60)
    descending = []
    for index, candle in enumerate(candles):
        price = Decimal(str(160 - index * 0.5))
        descending.append(
            candle.model_copy(
                update={
                    "open": price + Decimal("0.2"),
                    "high": price + Decimal("1"),
                    "low": price - Decimal("1"),
                    "close": price,
                }
            )
        )
    close = np.array([float(item.close) for item in descending])
    direction = np.ones(60, dtype=int)
    direction[-1] = -1
    ema26 = np.full(60, 132.0)
    ema9 = np.full(60, 133.0)
    ema9[-1] = 131.0
    _mock_ema(monkeypatch, ema9, ema26)
    mock_history.return_value = descending
    mock_rsi.return_value = np.full(60, 55.0)
    mock_supertrend.return_value = (
        close + 3,
        direction,
        np.full(60, 2.0),
    )

    result = calc_score("600519")

    assert result.state == "sell"
    assert result.confirmation is not None
    assert result.confirmation.age_bars == 0
    assert [trigger.code for trigger in result.triggers] == [
        "supertrend_bearish_reversal",
        "ema_bearish_crossover",
    ]
    assert result.risk is None


@pytest.mark.parametrize("trigger_source", ["supertrend", "ema"])
@patch("stk.services.score._calc_supertrend_arrays")
@patch("stk.services.score.talib.RSI")
@patch("stk.services.score.get_history")
def test_single_bearish_reversal_event_is_enough_for_sell(
    mock_history,
    mock_rsi,
    mock_supertrend,
    make_candles,
    monkeypatch,
    trigger_source,
):
    candles = make_candles(60)
    close = np.array([float(item.close) for item in candles])
    direction = np.ones(60, dtype=int)
    ema26 = np.full(60, 127.0)
    ema9 = np.full(60, 128.0)
    if trigger_source == "supertrend":
        direction[-1] = -1
        expected_code = "supertrend_bearish_reversal"
    else:
        ema9[-1] = 126.0
        expected_code = "ema_bearish_crossover"
    _mock_ema(monkeypatch, ema9, ema26)
    mock_history.return_value = candles
    mock_rsi.return_value = np.full(60, 55.0)
    mock_supertrend.return_value = (
        close + np.where(direction > 0, -3, 3),
        direction,
        np.full(60, 2.0),
    )

    result = calc_score("600519")

    assert result.state == "sell"
    assert result.confirmation is not None
    assert result.confirmation.age_bars == 0
    assert [trigger.code for trigger in result.triggers] == [expected_code]


@patch("stk.services.score._calc_supertrend_arrays")
@patch("stk.services.score.talib.RSI")
@patch("stk.services.score.get_history")
def test_overheated_trend_stays_watch(
    mock_history,
    mock_rsi,
    mock_supertrend,
    make_candles,
    monkeypatch,
):
    candles = make_candles(60)
    close = np.array([float(item.close) for item in candles])
    direction = -np.ones(60, dtype=int)
    direction[-1] = 1
    ema26 = np.full(60, 127.0)
    ema9 = np.full(60, 126.0)
    ema9[-1] = 128.0
    _mock_ema(monkeypatch, ema9, ema26)
    mock_history.return_value = candles
    mock_rsi.return_value = np.full(60, 75.0)
    mock_supertrend.return_value = (
        close - 3,
        direction,
        np.full(60, 2.0),
    )

    result = calc_score("600519")

    assert result.state == "watch"
    assert result.triggers[0].code == "supertrend_bullish_reversal"
    assert any("过热" in reason for reason in result.reasons)


@patch("stk.services.score._calc_supertrend_arrays")
@patch("stk.services.score.talib.RSI")
@patch("stk.services.score.get_history")
def test_established_bullish_trend_is_not_a_buy_signal(
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

    assert result.state == "ignored"
    assert result.triggers == []


@patch("stk.services.score._calc_supertrend_arrays")
@patch("stk.services.score.talib.RSI")
@patch("stk.services.score.get_history")
def test_bearish_event_replaces_a_recent_bullish_confirmation(
    mock_history,
    mock_rsi,
    mock_supertrend,
    make_candles,
    monkeypatch,
):
    candles = make_candles(60)
    close = np.array([float(item.close) for item in candles])
    direction = -np.ones(60, dtype=int)
    direction[-2] = 1
    ema26 = np.full(60, 127.0)
    ema9 = np.full(60, 126.0)
    ema9[-2:] = 128.0
    _mock_ema(monkeypatch, ema9, ema26)
    mock_history.return_value = candles
    mock_rsi.return_value = np.full(60, 55.0)
    mock_supertrend.return_value = (
        close + 3,
        direction,
        np.full(60, 2.0),
    )

    result = calc_score("600519")

    assert result.state == "sell"
    assert result.confirmation is not None
    assert result.confirmation.age_bars == 0
    assert [trigger.code for trigger in result.triggers] == [
        "supertrend_bearish_reversal"
    ]


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
