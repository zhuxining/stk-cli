"""ETF rotation factor, stage, action, and routing tests."""

from types import SimpleNamespace

from longport.openapi import SecuritiesUpdateMode
import numpy as np
import pandas as pd
import pytest

from stk.errors import StkError
from stk.models.rotation import RotationResult, RotationSignal, RotationSummary
from stk.services import rotation


def test_percentile_is_zero_to_one_hundred_and_ties_are_neutral():
    assert rotation.percentile(pd.Series([1.0, 2.0, 3.0])).tolist() == [0.0, 50.0, 100.0]
    assert rotation.percentile(pd.Series([4.0, 4.0, 4.0])).tolist() == [50.0, 50.0, 50.0]


@pytest.mark.parametrize(
    ("strength", "momentum", "expected"),
    [
        (50, 55, "emerging"),
        (50, 54.999, "lagging"),
        (50.001, 45, "leading"),
        (50.001, 44.999, "weakening"),
    ],
)
def test_stage_boundaries(strength, momentum, expected):
    assert rotation.classify_stage(strength, momentum) == expected


@pytest.mark.parametrize(
    ("stage", "momentum", "trend", "signal", "st_bull", "ema_bull", "expected"),
    [
        (
            "weakening",
            20,
            "bearish",
            RotationSignal(supertrend_bearish_event=True),
            False,
            False,
            "exit",
        ),
        (
            "emerging",
            55,
            "neutral",
            RotationSignal(supertrend_bullish_event=True, entry_eligible=True),
            True,
            False,
            "rotate_in",
        ),
        ("leading", 50, "bullish", RotationSignal(), True, True, "hold"),
        ("weakening", 30, "neutral", RotationSignal(), True, False, "reduce"),
        ("emerging", 60, "neutral", RotationSignal(), False, False, "watch"),
        ("lagging", 10, "bearish", RotationSignal(), False, False, "avoid"),
    ],
)
def test_action_priority(stage, momentum, trend, signal, st_bull, ema_bull, expected):
    assert (
        rotation.determine_action(
            stage,
            momentum,
            trend,
            signal,
            supertrend_bullish=st_bull,
            ema_bullish=ema_bull,
        )
        == expected
    )


def test_indicator_point_uses_talib_and_stockstats_ten_three():
    count = 90
    x = np.arange(count, dtype=float)
    frame = pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=count, freq="B").astype(str),
        "open": 100 + x * 0.2,
        "high": 101 + x * 0.2,
        "low": 99 + x * 0.2,
        "close": 100 + x * 0.2,
        "volume": 1_000_000 + x * 1_000,
        "turnover": (100 + x * 0.2) * (1_000_000 + x * 1_000),
    })

    point = rotation._indicator_point(
        rotation._Series(symbol="510300.SH", name="ETF", frame=frame),
        count - 1,
    )

    expected_return = frame.close.iloc[-1] / frame.close.iloc[-21] - 1
    assert point.metrics["return20"] == pytest.approx(expected_return)
    assert point.metrics["atr10"] > 0
    assert np.isfinite(point.metrics["mfi14"])
    assert len(point.supertrend_direction) == count


def _empty_result() -> RotationResult:
    return RotationResult(
        sources=[],
        summary=RotationSummary(
            total=0,
            analyzed=0,
            failed=0,
            emerging=0,
            leading=0,
            weakening=0,
            lagging=0,
        ),
    )


def test_route_calculates_before_replacing_all_targets(monkeypatch):
    calls: list[tuple[str, list[str], object]] = []
    monkeypatch.setattr(rotation, "rotate_pools", lambda sources: _empty_result())
    monkeypatch.setattr(
        rotation,
        "add_symbols",
        lambda group, symbols, mode: calls.append((group, symbols, mode)),
    )

    routed = rotation.route_rotation(
        ["theme", "asset"],
        emerging="emerging",
        leading="leading",
        weakening="weakening",
        lagging="lagging",
    )

    assert [call[0] for call in calls] == ["emerging", "leading", "weakening", "lagging"]
    assert all(call[2] == SecuritiesUpdateMode.Replace for call in calls)
    assert routed.mode == "replace"


def test_duplicate_source_symbols_fail_before_analysis(monkeypatch):
    monkeypatch.setattr(
        rotation,
        "get_watchlist",
        lambda group: SimpleNamespace(
            securities=[SimpleNamespace(symbol="510300.SH", name=group)]
        ),
    )
    monkeypatch.setattr(
        rotation,
        "_analyze_pool",
        lambda *args: pytest.fail("duplicate symbols must stop before analysis"),
    )

    with pytest.raises(StkError, match="Duplicate symbol"):
        rotation.rotate_pools(["theme", "asset"])


def test_source_target_overlap_never_calculates_or_mutates(monkeypatch):
    monkeypatch.setattr(
        rotation,
        "rotate_pools",
        lambda sources: pytest.fail("invalid groups must stop before calculation"),
    )

    with pytest.raises(StkError, match="must all be different"):
        rotation.route_rotation(
            ["theme", "asset"],
            emerging="theme",
            leading="leading",
            weakening="weakening",
            lagging="lagging",
        )
