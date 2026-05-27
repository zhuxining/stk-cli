"""Tests for intraday live scan service."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest

from stk.errors import IndicatorError
from stk.models.history import Candlestick
from stk.models.quote import Quote
from stk.models.score import (
    Decision,
    DecisionSignal,
    PrimarySignal,
    RiskProfile,
    ScoreResult,
    SignalContext,
)
from stk.services.live_scan import live_summary


def _intraday_candles() -> list[Candlestick]:
    base_time = datetime(2024, 1, 2, 1, 30, tzinfo=UTC)
    closes = [100 + (0.2 if index % 2 else -0.2) for index in range(39)] + [100.8]
    candles: list[Candlestick] = []
    for index, close in enumerate(closes):
        volume = 3000 if index == len(closes) - 1 else 1000
        candles.append(
            Candlestick(
                date=(base_time + timedelta(minutes=15 * index)).isoformat(),
                open=Decimal(str(close - 0.05)),
                high=Decimal(str(close + 0.1)),
                low=Decimal(str(close - 0.1)),
                close=Decimal(str(close)),
                volume=volume,
                turnover=Decimal(str(close * volume)),
            )
        )
    return candles


def _score(signal: DecisionSignal = "趋势买入") -> ScoreResult:
    return ScoreResult(
        symbol="600519.SH",
        decision=Decision(
            signal=signal,
            strength="普通信号",
            signal_status="new",
            signal_date="2026-05-25",
            bars_since_signal=0,
        ),
        primary_signal=PrimarySignal(
            ema9=10,
            ema26=9,
            supertrend=8,
            supertrend_direction="bullish",
            reasons=["test"],
        ),
        context=SignalContext(overall_bias="supportive"),
        risk=RiskProfile(atr=1, stop_loss=8, take_profit=12, risk_reward_ratio=2),
    )


@patch("stk.services.live_scan.get_realtime_quotes")
@patch("stk.services.live_scan.get_uncached_history")
@patch("stk.services.live_scan.calc_score")
def test_live_summary_returns_intraday_follow_signal(mock_score, mock_history, mock_quotes):
    mock_score.return_value = _score()
    mock_history.return_value = _intraday_candles()
    mock_quotes.return_value = [
        Quote(symbol="600519.SH", name="贵州茅台", last=Decimal("100.8"), change_pct=Decimal("0.8"))
    ]

    result = live_summary(["600519"], timeframe="15m")

    assert result.mode == "live"
    assert result.summary.focus_count == 1
    assert result.summary.follow_count == 1
    assert result.focus[0].symbol == "600519.SH"
    assert result.focus[0].daily_signal == "趋势买入"
    assert result.focus[0].live_signal == "实时跟随"
    assert result.focus[0].risk_line is not None
    mock_history.assert_called_once_with("600519.SH", period="15m", count=80)


@patch("stk.services.live_scan.get_realtime_quotes", return_value=[])
@patch("stk.services.live_scan.get_uncached_history")
@patch("stk.services.live_scan.calc_score")
def test_live_summary_skips_daily_observe(mock_score, mock_history, _mock_quotes):
    mock_score.return_value = _score(signal="观察")

    result = live_summary(["600519"], timeframe="15m")

    assert result.summary.focus_count == 0
    assert result.ignored.no_live_signal_count == 1
    mock_history.assert_not_called()


def test_live_summary_rejects_unsupported_timeframe():
    with pytest.raises(IndicatorError, match="Unsupported live timeframe"):
        live_summary(["600519"], timeframe="1m")
