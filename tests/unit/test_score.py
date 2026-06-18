"""Tests for trend-first signal scoring service."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from stk.errors import IndicatorError
from stk.models.history import Candlestick
from stk.models.score import ContextFactor, FactorState, SignalContext
from stk.services.score import (
    _calc_money_flow_factor,
    _check_low_volume_cross,
    _closed_daily_df,
    calc_score,
)


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


def _setup_context(
    *,
    trigger_name: str | None = None,
    trigger_state: FactorState = "opportunity",
    confirming: tuple[str, ...] = (),
) -> SignalContext:
    factors = [
        ContextFactor(name=name, state="confirming", metrics={"bias": "confirming"})
        for name in confirming
    ]
    if trigger_name is not None:
        factors.insert(
            0,
            ContextFactor(
                name=trigger_name,
                state=trigger_state,
                metrics={"trigger": True},
            ),
        )
    return SignalContext(overall_bias="supportive", factors=factors)


def _neutral_context() -> SignalContext:
    return SignalContext(
        overall_bias="mixed",
        factors=[
            ContextFactor(name="momentum", state="neutral", metrics={"rsi_zone": "neutral"}),
            ContextFactor(name="macd", state="neutral", metrics={"bias": "neutral"}),
        ],
    )


def test_closed_daily_df_drops_current_cn_bar_before_close():
    df = pd.DataFrame({"date": ["2026-05-25 00:00:00", "2026-05-26 00:00:00"]})
    now = datetime(2026, 5, 26, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai"))

    result = _closed_daily_df(df, "600519.SH", now=now)

    assert result["date"].tolist() == ["2026-05-25 00:00:00"]


def test_closed_daily_df_keeps_current_cn_bar_after_close():
    df = pd.DataFrame({"date": ["2026-05-25 00:00:00", "2026-05-26 00:00:00"]})
    now = datetime(2026, 5, 26, 15, 30, tzinfo=ZoneInfo("Asia/Shanghai"))

    result = _closed_daily_df(df, "600519.SH", now=now)

    assert result["date"].tolist() == ["2026-05-25 00:00:00", "2026-05-26 00:00:00"]


@patch("stk.services.score.get_history")
def test_calc_score_basic(mock_history, make_candles):
    """Test basic scoring returns the monitoring structure."""
    mock_history.return_value = make_candles(60)

    result = calc_score("600519")

    assert result.symbol == "600519"
    assert result.decision.strength in {"推荐", "预警", None}
    assert result.decision.signal in {
        "趋势买入",
        "趋势退出",
        "超卖修复",
        "观察",
    }
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
def test_trend_buy_signal(mock_history):
    """EMA9 golden cross plus bullish Supertrend yields a trend buy focus."""
    mock_history.return_value = _strong_buy_candles()

    result = calc_score("600519")

    assert result.decision.strength == "推荐"
    assert result.decision.signal == "趋势买入"
    assert result.decision.signal_status == "new"
    assert result.decision.bars_since_signal == 0
    assert result.primary_signal.ema_cross == "golden"


@patch("stk.services.score.get_history")
def test_trend_sell_signal(mock_history):
    """EMA9 death cross plus bearish Supertrend yields a trend exit focus."""
    mock_history.return_value = _strong_sell_candles()

    result = calc_score("600519")

    assert result.decision.strength == "预警"
    assert result.decision.signal == "趋势退出"
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


@patch("stk.services.score._build_context", return_value=_neutral_context())
@patch("stk.services.score.get_history")
def test_mismatch_holds_signal(mock_history, _mock_context):
    """EMA and Supertrend disagreement stays observational without a confirmed pattern."""
    mock_history.return_value = _mismatch_candles()

    result = calc_score("600519")

    assert result.decision.strength is None
    assert result.decision.signal == "观察"
    assert any("方向不一致" in reason for reason in result.primary_signal.reasons)


@patch("stk.services.score.get_history")
def test_old_cross_no_strong_signal(mock_history):
    """A stale alignment without a recent trigger does not become a buy signal."""
    mock_history.return_value = _stale_bullish_candles()

    result = calc_score("600519")

    assert result.decision.strength is None
    assert result.decision.signal == "观察"
    assert result.decision.signal_status == "stale"
    assert result.decision.bars_since_signal is None


@patch("stk.services.score._build_context")
@patch("stk.services.score.get_history")
def test_oversold_repair_signal_requires_repair_confirmations(mock_history, mock_context):
    """Oversold repair needs an oversold trigger plus price/indicator repair."""
    mock_history.return_value = _mismatch_candles()
    bullish_context = SignalContext(
        overall_bias="supportive",
        factors=[
            ContextFactor(
                name="momentum",
                state="opportunity",
                metrics={"rsi14": 32, "j": 8, "kdj_bias": "bullish"},
            ),
            ContextFactor(name="macd", state="confirming", metrics={"hist": 0.2}),
            ContextFactor(name="boll", state="neutral", metrics={"position_pct": 22}),
            ContextFactor(
                name="volume_price", state="confirming", metrics={"volume_ratio_5d": 1.6}
            ),
            ContextFactor(
                name="ema_trend",
                state="confirming",
                metrics={"ema5": 100, "ema10": 99, "ema20": 98},
            ),
            ContextFactor(name="money_flow", state="neutral", metrics={"mfi14": 45}),
            ContextFactor(name="divergence", state="none", metrics={"type": "none"}),
        ],
    )

    def _context_side_effect(*_args, **kwargs) -> SignalContext:
        return bullish_context if kwargs["direction"] == "bullish" else _neutral_context()

    mock_context.side_effect = _context_side_effect

    result = calc_score("600519")

    assert result.decision.signal == "超卖修复"
    assert result.decision.strength == "推荐"
    assert result.decision.signal_status == "new"


@patch("stk.services.score._build_context")
@patch("stk.services.score.get_history")
def test_oversold_without_repair_stays_watch(mock_history, mock_context):
    """Oversold alone is not enough to create a repair signal."""
    mock_history.return_value = _mismatch_candles()
    weak_context = SignalContext(
        overall_bias="mixed",
        factors=[
            ContextFactor(
                name="momentum",
                state="opportunity",
                metrics={"rsi14": 30, "j": 5, "kdj_bias": "bearish"},
            ),
            ContextFactor(name="macd", state="neutral", metrics={"hist": -0.2}),
            ContextFactor(name="ema_trend", state="neutral", metrics={"ema5": 120}),
        ],
    )

    def _context_side_effect(*_args, **kwargs) -> SignalContext:
        return weak_context if kwargs["direction"] == "bullish" else _neutral_context()

    mock_context.side_effect = _context_side_effect

    result = calc_score("600519")

    assert result.decision.signal == "观察"


@patch("stk.services.score._build_context")
@patch("stk.services.score.get_history")
def test_single_reversal_trigger_stays_watch(mock_history, mock_context):
    """Single oversold/divergence style triggers do not become focus signals."""
    mock_history.return_value = _mismatch_candles()
    weak_context = _setup_context(trigger_name="divergence", trigger_state="opportunity")

    def _context_side_effect(*_args, **kwargs) -> SignalContext:
        return weak_context if kwargs["direction"] == "bullish" else _neutral_context()

    mock_context.side_effect = _context_side_effect

    result = calc_score("600519")

    assert result.decision.signal == "观察"


@patch("stk.services.score._build_context", return_value=_neutral_context())
@patch("stk.services.score.get_history")
def test_neutral_context_stays_watch(mock_history, _mock_context):
    """Pure neutral context does not create a synthetic pattern."""
    mock_history.return_value = _mismatch_candles()

    result = calc_score("600519")

    assert result.decision.signal == "观察"


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


def test_low_volume_golden_cross_adds_warning():
    """Low volume golden cross should trigger a validity warning."""
    df = pd.DataFrame({
        "turnover": [1000000.0, 1100000.0, 1050000.0, 1080000.0, 1020000.0, 500000.0],
    })
    reasons: list[str] = []
    _check_low_volume_cross(df, reasons)
    assert len(reasons) == 1
    assert "缩量金叉" in reasons[0]
    assert "0.5" in reasons[0]  # vol_ratio ≈ 0.48


def test_normal_volume_golden_cross_no_warning():
    """Normal volume golden cross should not trigger warning."""
    df = pd.DataFrame({
        "turnover": [1000000.0, 1000000.0, 1000000.0, 1000000.0, 1000000.0, 1000000.0],
    })
    reasons: list[str] = []
    _check_low_volume_cross(df, reasons)
    assert len(reasons) == 0


def test_insufficient_turnover_data_no_warning():
    """Less than 6 bars should skip the check silently."""
    df = pd.DataFrame({"turnover": [1000000.0, 500000.0]})
    reasons: list[str] = []
    _check_low_volume_cross(df, reasons)
    assert len(reasons) == 0
