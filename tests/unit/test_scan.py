"""Tests for current buy/sell scan output."""

from decimal import Decimal

from stk.models.quote import Quote
from stk.models.score import (
    QualitySummary,
    SignalConfirmation,
    SignalIndicators,
    SignalRisk,
    SignalTrigger,
    StockAssessment,
)
from stk.services.scan import _monitor_symbols


def _assessment(
    symbol: str,
    state: str,
    *,
    turnover_ratio: float = 1,
    with_details: bool = False,
) -> StockAssessment:
    trigger = []
    if state in {"buy", "sell"}:
        trigger = [
            SignalTrigger(
                code=(
                    "supertrend_bullish_reversal"
                    if state == "buy"
                    else "supertrend_bearish_reversal"
                ),
                occurred_at="2026-07-29",
                age_bars=0,
            )
        ]
    return StockAssessment(
        symbol=symbol,
        as_of="2026-07-29",
        state=state,
        triggers=trigger,
        confirmation=(
            SignalConfirmation(confirmed_at="2026-07-29", age_bars=0)
            if state in {"buy", "sell"}
            else None
        ),
        reasons=["测试原因"],
        indicators=SignalIndicators(
            close=100,
            ema9=99,
            ema26=95,
            supertrend=92,
            supertrend_direction="bearish" if state == "sell" else "bullish",
            rsi14=55,
            atr10=2,
            turnover_ratio_5d=turnover_ratio,
            max_entry_price=102 if state == "buy" else None,
        ),
        quality=QualitySummary(
            bias="supportive",
            factors=[] if with_details else None,
        ),
        risk=SignalRisk(stop_loss=96, trailing_stop=92) if state == "buy" else None,
        recent_bars=[] if with_details else None,
    )


def test_monitor_returns_mutually_exclusive_counts(monkeypatch):
    assessments = {
        "buy": _assessment("600519.SH", "buy"),
        "sell": _assessment("000001.SZ", "sell"),
        "watch": _assessment("700.HK", "watch"),
        "ignored": _assessment("AAPL.US", "ignored"),
    }
    monkeypatch.setattr(
        "stk.services.scan.calc_score",
        lambda symbol, **kwargs: assessments[symbol],
    )
    monkeypatch.setattr(
        "stk.services.scan.get_realtime_quotes",
        lambda symbols: [
            Quote(
                symbol="600519.SH",
                name="贵州茅台",
                last=Decimal("1500"),
                change_pct=Decimal("1.2"),
            )
        ],
    )

    result = _monitor_symbols(
        list(assessments),
        {"600519.SH": "贵州茅台"},
        group="core",
    )

    assert result.summary.model_dump() == {
        "total": 4,
        "analyzed": 4,
        "failed": 0,
        "buy": 1,
        "sell": 1,
        "watch": 1,
        "ignored": 1,
    }
    assert result.buy[0].quote is not None
    assert result.buy[0].signal.confirmation.age_bars == 0
    assert result.buy[0].signal.triggers[0].code == "supertrend_bullish_reversal"
    assert result.buy[0].signal.triggers[0].age_bars == 0
    assert result.sell[0].risk is None


def test_monitor_returns_partial_failures(monkeypatch):
    def fake_score(symbol: str, **kwargs):
        if symbol == "bad":
            raise RuntimeError("boom")
        return _assessment("600519.SH", "buy")

    monkeypatch.setattr("stk.services.scan.calc_score", fake_score)
    monkeypatch.setattr("stk.services.scan.get_realtime_quotes", lambda symbols: [])

    result = _monitor_symbols(["good", "bad"], {}, group="core")

    assert result.summary.total == 2
    assert result.summary.analyzed == 1
    assert result.summary.failed == 1
    assert result.failures[0].code == "runtime_error"
    assert result.failures[0].symbol == "bad"


def test_monitor_passes_detail_options_to_assessment(monkeypatch):
    calls: list[tuple[int, bool]] = []

    def fake_score(symbol: str, *, recent_bars: int, include_factors: bool):
        calls.append((recent_bars, include_factors))
        return _assessment("600519.SH", "buy", with_details=True)

    monkeypatch.setattr("stk.services.scan.calc_score", fake_score)
    monkeypatch.setattr("stk.services.scan.get_realtime_quotes", lambda symbols: [])

    result = _monitor_symbols(
        ["600519.SH"],
        {},
        group="core",
        recent_bars=5,
        include_factors=True,
    )

    assert calls == [(5, True)]
    assert result.buy[0].quality.factors == []
    assert result.buy[0].recent_bars == []


def test_buy_signals_sort_by_quality_then_turnover(monkeypatch):
    first = _assessment("A.US", "buy", turnover_ratio=1)
    second = _assessment("B.US", "buy", turnover_ratio=2)
    monkeypatch.setattr(
        "stk.services.scan.calc_score",
        lambda symbol, **kwargs: {"a": first, "b": second}[symbol],
    )
    monkeypatch.setattr("stk.services.scan.get_realtime_quotes", lambda symbols: [])

    result = _monitor_symbols(["a", "b"], {}, group="core")

    assert [item.symbol for item in result.buy] == ["B.US", "A.US"]
