"""Tests for daily monitoring scan service."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from stk.errors import IndicatorError
from stk.models.quote import Quote
from stk.models.score import (
    ContextBias,
    ContextFactor,
    Decision,
    DecisionAction,
    FactorState,
    PrimarySignal,
    RiskProfile,
    ScoreResult,
    SignalContext,
    SignalLevel,
    SignalStatus,
)
from stk.services.scan import batch_summary


def _score_result(
    symbol: str,
    *,
    level: SignalLevel,
    action: DecisionAction,
    status: SignalStatus,
    confidence: float,
    bias: ContextBias = "supportive",
    factor_state: FactorState = "confirming",
) -> ScoreResult:
    return ScoreResult(
        symbol=symbol,
        decision=Decision(
            action=action,
            level=level,
            direction="bullish" if action != "focus_sell" else "bearish",
            confidence=confidence,
            signal_status=status,
            signal_date="2026-05-12",
            bars_since_signal=1,
        ),
        primary_signal=PrimarySignal(
            ema_cross="golden" if action != "focus_sell" else "death",
            ema9=10,
            ema26=9,
            supertrend=8,
            supertrend_direction="bullish" if action != "focus_sell" else "bearish",
            adx=25,
            reasons=["test reason"],
        ),
        context=SignalContext(
            overall_bias=bias,
            factors=[
                ContextFactor(
                    name="momentum",
                    state=factor_state,
                    metrics={"rsi14": 55, "rsi_zone": "neutral"},
                )
            ],
            warnings=[],
        ),
        risk=RiskProfile(
            atr=1,
            stop_loss=8,
            take_profit=12,
            risk_reward_ratio=2,
            risk_level="low",
        ),
    )


@patch("stk.services.scan.get_realtime_quotes")
@patch("stk.services.scan.get_daily")
@patch("stk.services.scan.calc_score")
def test_batch_summary_returns_focus_only(mock_score, mock_daily, mock_quotes):
    """Only active signal candidates enter focus output."""
    mock_quotes.return_value = [
        Quote(symbol="600519.SH", name="贵州茅台", last=Decimal(100)),
        Quote(symbol="000001.SZ", name="平安银行", last=Decimal(10)),
    ]
    mock_daily.return_value = SimpleNamespace(
        days=[
            {
                "date": "2026-05-14",
                "open": 99.0,
                "high": 102.0,
                "low": 98.0,
                "close": 100.0,
                "volume": 1000000,
                "turnover": 100000000.0,
                "change_pct": 1.23,
                "EMA9": 98.5,
                "EMA26": 95.1,
                "Supertrend": 92.0,
                "SupertrendDirection": "bullish",
                "MACD": 1.2,
                "signal": 1.0,
                "hist": 0.2,
                "RSI": 55.0,
                "J": 68.0,
                "upper": 105.0,
                "lower": 90.0,
                "ATR10": 2.1,
            }
        ]
    )

    def _score(symbol: str) -> ScoreResult:
        if symbol == "300750.SZ":
            raise IndicatorError("history_unavailable")
        if symbol == "600519.SH":
            return _score_result(
                symbol,
                level="strong_buy",
                action="focus_buy",
                status="new",
                confidence=92,
            )
        return _score_result(
            symbol,
            level="hold",
            action="watch",
            status="stale",
            confidence=35,
            bias="mixed",
            factor_state="neutral",
        )

    mock_score.side_effect = _score

    result = batch_summary(["600519.SH", "000001.SZ", "300750.SZ"])

    assert result.universe.total == 3
    assert result.universe.scanned == 2
    assert result.universe.failed == 1
    assert result.summary.focus_count == 1
    assert result.summary.high_priority_count == 1
    assert result.summary.entry_signal_count == 1
    assert result.ignored.no_signal_count == 1
    assert result.errors[0].symbol == "300750.SZ"
    assert result.focus[0].symbol == "600519.SH"
    assert result.focus[0].priority == "high"
    assert result.focus[0].decision.action == "focus_buy"
    assert result.focus[0].daily10 == [
        {
            "date": "2026-05-14",
            "open": 99.0,
            "high": 102.0,
            "low": 98.0,
            "close": 100.0,
            "volume": 1000000,
            "turnover": 100000000.0,
            "change_pct": 1.23,
            "ema9": 98.5,
            "ema26": 95.1,
            "supertrend": 92.0,
            "supertrend_direction": "bullish",
            "macd": 1.2,
            "macd_signal": 1.0,
            "macd_hist": 0.2,
            "rsi14": 55.0,
            "j": 68.0,
            "atr10": 2.1,
            "boll_position_pct": 66.7,
        }
    ]
    mock_daily.assert_called_once_with("600519.SH", count=10)


@patch("stk.services.scan.get_realtime_quotes")
@patch("stk.services.scan.calc_score")
def test_hold_with_risk_context_enters_watch_focus(mock_score, mock_quotes):
    """Hold decisions can still enter focus when context contains risk or opportunity."""
    mock_quotes.return_value = []
    mock_score.return_value = _score_result(
        "000001.SZ",
        level="hold",
        action="watch",
        status="stale",
        confidence=35,
        bias="risky",
        factor_state="risk",
    )

    result = batch_summary(["000001.SZ"])

    assert result.summary.focus_count == 1
    assert result.summary.watch_signal_count == 1
    assert result.focus[0].priority == "low"
    assert result.focus[0].decision.action == "watch"
