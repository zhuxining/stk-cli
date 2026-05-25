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
    DecisionIntent,
    FactorState,
    PrimarySignal,
    RiskProfile,
    ScoreResult,
    SignalContext,
    SignalStatus,
    SignalStrength,
)
from stk.services.scan import batch_summary


def _score_result(
    symbol: str,
    *,
    strength: SignalStrength,
    intent: DecisionIntent,
    status: SignalStatus,
    bias: ContextBias = "supportive",
    factor_state: FactorState = "confirming",
    bars_since_signal: int | None = 1,
) -> ScoreResult:
    return ScoreResult(
        symbol=symbol,
        decision=Decision(
            intent=intent,
            strength=strength,
            pattern="趋势共振",
            signal_status=status,
            signal_date="2026-05-12",
            bars_since_signal=bars_since_signal,
        ),
        primary_signal=PrimarySignal(
            ema_cross="death" if intent == "风险退出" else "golden",
            ema9=10,
            ema26=9,
            supertrend=8,
            supertrend_direction="bearish" if intent == "风险退出" else "bullish",
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


def _daily_result() -> SimpleNamespace:
    return SimpleNamespace(
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


def _compact_daily10() -> list[dict[str, str | int | float | None]]:
    return [
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


@patch("stk.services.scan.get_realtime_quotes")
@patch("stk.services.scan.get_daily")
@patch("stk.services.scan.calc_score")
def test_batch_summary_returns_focus_only(mock_score, mock_daily, mock_quotes):
    """Only active signal candidates enter focus output."""
    mock_quotes.return_value = [
        Quote(symbol="600519.SH", name="贵州茅台", last=Decimal(100)),
        Quote(symbol="000001.SZ", name="平安银行", last=Decimal(10)),
    ]

    def _score(symbol: str) -> ScoreResult:
        if symbol == "300750.SZ":
            raise IndicatorError("history_unavailable")
        if symbol == "600519.SH":
            return _score_result(
                symbol,
                strength="强信号",
                intent="买入关注",
                status="new",
            )
        return _score_result(
            symbol,
            strength="无信号",
            intent="观察",
            status="stale",
            bias="mixed",
            factor_state="neutral",
        )

    mock_score.side_effect = _score

    result = batch_summary(["600519.SH", "000001.SZ", "300750.SZ"])

    assert result.universe.total == 3
    assert result.universe.scanned == 2
    assert result.universe.failed == 1
    assert result.summary.focus_count == 1
    assert result.summary.strong_signal_count == 1
    assert result.summary.entry_signal_count == 1
    assert result.ignored.no_signal_count == 1
    assert result.errors[0].symbol == "300750.SZ"
    assert result.focus[0].symbol == "600519.SH"
    assert result.focus[0].decision.intent == "买入关注"
    assert {item.decision.intent for item in result.focus} <= {"买入关注", "风险退出"}
    assert result.focus[0].daily10 is None
    mock_daily.assert_not_called()


@patch("stk.services.scan.get_realtime_quotes")
@patch("stk.services.scan.get_daily")
@patch("stk.services.scan.calc_score")
def test_batch_summary_includes_daily10_when_requested(mock_score, mock_daily, mock_quotes):
    """Strong signals include daily10 only when explicitly requested."""
    mock_quotes.return_value = [Quote(symbol="600519.SH", name="贵州茅台", last=Decimal(100))]
    mock_daily.return_value = _daily_result()
    mock_score.return_value = _score_result(
        "600519.SH",
        strength="强信号",
        intent="买入关注",
        status="new",
    )

    result = batch_summary(["600519.SH"], include_daily10=True)

    assert result.focus[0].daily10 == _compact_daily10()
    mock_daily.assert_called_once_with("600519.SH", count=10)


@patch("stk.services.scan.get_realtime_quotes")
@patch("stk.services.scan.calc_score")
def test_batch_summary_compacts_context_by_default(mock_score, mock_quotes):
    """Default scan output omits neutral/no-signal context factors."""
    mock_quotes.return_value = []
    score = _score_result(
        "600519.SH",
        strength="强信号",
        intent="买入关注",
        status="new",
    )
    score.context.factors = [
        ContextFactor(name="macd", state="confirming", metrics={"bias": "bullish"}),
        ContextFactor(name="volume_price", state="neutral", metrics={"volume_ratio_5d": 0.8}),
        ContextFactor(name="divergence", state="none", metrics={"type": "none"}),
        ContextFactor(name="boll", state="risk", metrics={"position_pct": 92.0}),
    ]
    mock_score.return_value = score

    compact = batch_summary(["600519.SH"])
    full = batch_summary(["600519.SH"], include_full_context=True)

    assert [factor.name for factor in compact.focus[0].context.factors] == ["macd", "boll"]
    assert [factor.name for factor in full.focus[0].context.factors] == [
        "macd",
        "volume_price",
        "divergence",
        "boll",
    ]


@patch("stk.services.scan.get_realtime_quotes")
@patch("stk.services.scan.calc_score")
def test_hold_with_risk_context_is_ignored(mock_score, mock_quotes):
    """Observational decisions are counted but no longer expanded in focus."""
    mock_quotes.return_value = []
    mock_score.return_value = _score_result(
        "000001.SZ",
        strength="无信号",
        intent="观察",
        status="stale",
        bias="risky",
        factor_state="risk",
        bars_since_signal=5,
    )

    result = batch_summary(["000001.SZ"])

    assert result.summary.focus_count == 0
    assert result.summary.watch_signal_count == 0
    assert result.ignored.no_signal_count == 1
    assert result.focus == []


@patch("stk.services.scan.get_realtime_quotes")
@patch("stk.services.scan.calc_score")
def test_old_hold_with_single_risk_context_is_ignored(mock_score, mock_quotes):
    """Old observational decisions stay out of focus."""
    mock_quotes.return_value = []
    mock_score.return_value = _score_result(
        "000001.SZ",
        strength="无信号",
        intent="观察",
        status="stale",
        bias="risky",
        factor_state="risk",
        bars_since_signal=20,
    )

    result = batch_summary(["000001.SZ"])

    assert result.summary.focus_count == 0
    assert result.ignored.no_signal_count == 1
