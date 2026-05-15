"""Tests for trend-first signal scoring service."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from stk.errors import IndicatorError
from stk.models.history import Candlestick
from stk.services.score import _calc_money_flow_factor, calc_score


def _candles_from_closes(closes: list[float], *, width: float = 1.0) -> list[Candlestick]:
    candles: list[Candlestick] = []
    for i, close in enumerate(closes):
        candles.append(
            Candlestick(
                date=(datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=i)).strftime("%Y-%m-%d"),
                open=Decimal(str(close)),
                high=Decimal(str(close + width)),
                low=Decimal(str(close - width)),
                close=Decimal(str(close)),
                volume=1000000 + i,
                turnover=Decimal(str(close * 1000000)),
            )
        )
    return candles


def _strong_buy_candles() -> list[Candlestick]:
    closes = [120 - i * 0.5 for i in range(55)] + [92 + i * 4.0 for i in range(6)]
    return _candles_from_closes(closes)


def _strong_sell_candles() -> list[Candlestick]:
    closes = [80 + i * 0.5 for i in range(55)] + [108 - i * 4.0 for i in range(6)]
    return _candles_from_closes(closes)


def _mismatch_candles() -> list[Candlestick]:
    closes = [80 + i * 0.7 for i in range(58)] + [120, 110]
    return _candles_from_closes(closes)


def _stale_bullish_candles() -> list[Candlestick]:
    closes = [80 + i * 0.5 for i in range(70)]
    return _candles_from_closes(closes)


@patch("stk.services.score.get_history")
def test_calc_score_basic(mock_history, make_candles):
    """Test basic scoring returns the monitoring structure."""
    mock_history.return_value = make_candles(60)

    result = calc_score("600519")

    assert result.symbol == "600519"
    assert result.decision.level in {"strong_buy", "buy", "hold", "sell", "strong_sell"}
    assert result.decision.action in {"focus_buy", "focus_sell", "watch"}
    assert result.context.overall_bias in {"supportive", "mixed", "conflicting", "risky"}
    assert result.risk.risk_level in {"low", "medium", "high"}


@patch("stk.services.score.get_history")
def test_score_dimensions_complete(mock_history, make_candles):
    """Test context factors are present and bounded."""
    mock_history.return_value = make_candles(60)

    result = calc_score("600519")

    factor_names = {factor.name for factor in result.context.factors}
    assert factor_names == {
        "momentum",
        "macd",
        "boll",
        "volume_price",
        "ema_trend",
        "money_flow",
        "divergence",
    }

    for factor in result.context.factors:
        assert factor.metrics
        assert factor.state in {
            "confirming",
            "neutral",
            "conflicting",
            "risk",
            "opportunity",
            "none",
        }


@patch("stk.services.score.get_history")
def test_score_atr_fields(mock_history, make_candles):
    """Test ATR-based trade points are calculated."""
    mock_history.return_value = make_candles(60)

    result = calc_score("600519")

    assert result.risk.atr is not None
    assert result.risk.atr > 0
    assert result.risk.stop_loss is not None
    assert result.risk.take_profit is not None
    assert result.risk.stop_loss < result.risk.take_profit
    assert result.risk.risk_reward_ratio is not None
    assert result.risk.risk_reward_ratio > 0


@patch("stk.services.score.get_history")
def test_score_insufficient_data(mock_history, make_candles):
    """Test error when insufficient history data."""
    mock_history.return_value = make_candles(10)

    with pytest.raises(IndicatorError, match="Insufficient"):
        calc_score("600519")


@patch("stk.services.score.get_history")
def test_score_no_data(mock_history):
    """Test error when no history data."""
    mock_history.return_value = []

    with pytest.raises(IndicatorError, match="Insufficient"):
        calc_score("600519")


@patch("stk.services.score.get_history")
def test_strong_buy_signal(mock_history):
    """EMA9 golden cross plus bullish Supertrend yields strong_buy."""
    mock_history.return_value = _strong_buy_candles()

    result = calc_score("600519")

    assert result.decision.level == "strong_buy"
    assert result.decision.action == "focus_buy"
    assert result.decision.signal_status == "new"
    assert result.decision.bars_since_signal == 0
    assert result.primary_signal.ema_cross == "golden"


@patch("stk.services.score.get_history")
def test_strong_sell_signal(mock_history):
    """EMA9 death cross plus bearish Supertrend yields strong_sell."""
    mock_history.return_value = _strong_sell_candles()

    result = calc_score("600519")

    assert result.decision.level == "strong_sell"
    assert result.decision.action == "focus_sell"
    assert result.decision.signal_status == "new"
    assert result.decision.bars_since_signal == 0
    assert result.primary_signal.ema_cross == "death"


@patch("stk.services.score.get_history")
def test_strong_sell_risk_points_are_bearish(mock_history):
    """Bearish signals use an upper invalidation line and lower downside reference."""
    candles = _strong_sell_candles()
    mock_history.return_value = candles

    result = calc_score("600519")
    current_price = float(candles[-1].close)

    assert result.risk.stop_loss is not None
    assert result.risk.take_profit is not None
    assert result.risk.stop_loss > current_price
    assert result.risk.take_profit < current_price
    assert result.risk.risk_reward_ratio is not None
    assert result.risk.risk_reward_ratio > 0


@patch("stk.services.score.get_history")
def test_mismatch_holds_signal(mock_history):
    """EMA and Supertrend disagreement stays at hold level."""
    mock_history.return_value = _mismatch_candles()

    result = calc_score("600519")

    assert result.decision.level == "hold"
    assert result.decision.action == "watch"
    assert any("方向不一致" in reason for reason in result.primary_signal.reasons)


@patch("stk.services.score.get_history")
def test_old_cross_no_strong_signal(mock_history):
    """A stale alignment without a recent trigger does not become a buy signal."""
    mock_history.return_value = _stale_bullish_candles()

    result = calc_score("600519")

    assert result.decision.level == "hold"
    assert result.decision.action == "watch"
    assert result.decision.signal_status == "stale"
    assert result.decision.bars_since_signal is None


@patch("stk.services.score.get_history")
def test_primary_signal_reasons_are_structured(mock_history):
    """Test primary signal keeps machine-readable evidence and concise reasons."""
    mock_history.return_value = _strong_buy_candles()

    result = calc_score("600519")

    assert result.primary_signal.reasons
    assert result.primary_signal.ema9 is not None
    assert result.primary_signal.ema26 is not None
    assert result.primary_signal.supertrend is not None


@patch("stk.services.score.get_history")
def test_score_adx(mock_history, make_candles):
    """Test ADX field is populated."""
    mock_history.return_value = make_candles(60)

    result = calc_score("600519")

    assert result.primary_signal.adx is not None


@patch("stk.services.score.talib.MFI")
def test_money_flow_factor_respects_direction(mock_mfi):
    """Strong MFI confirms bullish trends but conflicts with bearish trends."""
    mock_mfi.return_value = np.array([np.nan] * 14 + [65.0])
    series = pd.Series([10.0 + i for i in range(15)])

    bullish = _calc_money_flow_factor(series, series, series, series, direction="bullish")
    bearish = _calc_money_flow_factor(series, series, series, series, direction="bearish")

    assert bullish.state == "confirming"
    assert bearish.state == "conflicting"
