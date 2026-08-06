"""ETF rotation v2 state, action, indicator, and routing tests."""

from types import SimpleNamespace

from longport.openapi import SecuritiesUpdateMode
import numpy as np
import pandas as pd
import pytest

from stk.errors import StkError
from stk.models.rotation import RotationResult, RotationSummary
from stk.services import rotation


def _point(
    *,
    direction: int = 1,
    flip: str | None = None,
    **updates: float,
) -> rotation._Point:
    length = 30
    index = length - 1
    directions = np.full(length, direction, dtype=int)
    if flip == "bullish":
        directions[:-1] = -1
        directions[-1] = 1
    elif flip == "bearish":
        directions[:-1] = 1
        directions[-1] = -1
    metrics = {
        "return5": 0.04,
        "previous_return5": 0.01,
        "return20": 0.08,
        "return60": 0.1,
        "vol20": 0.1,
        "vol60": 0.15,
        "slope20": 0.002,
        "correlation20": 0.9,
        "ema5": 104.0,
        "ema9": 103.0,
        "ema10": 102.0,
        "ema20": 100.0,
        "ema26": 99.0,
        "ema60": 95.0,
        "ema20_slope5": 0.02,
        "rsi14": 60.0,
        "adx14": 25.0,
        "mfi14": 60.0,
        "macd": 1.0,
        "macd_signal": 0.8,
        "macd_hist": 0.2,
        "close": 105.0,
        "atr10": 3.0,
        "supertrend": 98.0,
        "entry_distance_atr": 5 / 3,
        "turnover_ratio": 1.2,
    }
    metrics.update(updates)
    close = np.full(length, metrics["close"])
    ema9 = np.full(length, metrics["ema9"])
    ema26 = np.full(length, metrics["ema26"])
    return rotation._Point(
        series=rotation._Series(
            symbol="510300.SH",
            name="ETF",
            frame=pd.DataFrame({"date": [f"d{i}" for i in range(length)]}),
        ),
        index=index,
        metrics=metrics,
        close=close,
        ema9=ema9,
        ema26=ema26,
        supertrend_direction=directions,
    )


def _strong_history() -> list[rotation._Point]:
    return [_point() for _ in range(12)]


def test_percentile_is_zero_to_one_hundred_and_ties_are_neutral():
    assert rotation.percentile(pd.Series([1.0, 2.0, 3.0])).tolist() == [0.0, 50.0, 100.0]
    assert rotation.percentile(pd.Series([4.0, 4.0, 4.0])).tolist() == [50.0, 50.0, 50.0]


def test_confirmed_emerging_has_priority_over_strong():
    result = rotation.classify_state(_point(flip="bullish"), _strong_history())

    assert result.state == "emerging"
    assert result.setup == "confirmed"


@pytest.mark.parametrize(("age", "expected"), [(0, True), (1, True), (2, False)])
def test_confirmed_emerging_uses_two_bar_event_window(age, expected):
    point = _point()
    point.supertrend_direction[:] = -1
    flip_index = point.index - age
    point.supertrend_direction[flip_index:] = 1

    signal = rotation._events(point)

    assert signal.supertrend_bullish_event is expected
    assert signal.supertrend_bullish_age == age


def test_rebound_emerging_accepts_early_recovery_without_supertrend_confirmation():
    point = _point(
        direction=-1,
        close=100.0,
        ema9=99.0,
        ema20=101.0,
        atr10=4.0,
        return5=0.05,
        previous_return5=-0.03,
    )

    result = rotation.classify_state(point, [])

    assert result.state == "emerging"
    assert result.setup == "rebound"


def test_established_absolute_uptrend_is_strong():
    result = rotation.classify_state(_point(), [])

    assert result.state == "strong"
    assert result.setup is None


def test_long_term_weakness_is_not_fading_without_recent_active_history():
    point = _point(
        direction=-1,
        close=90.0,
        ema5=91.0,
        ema10=92.0,
        ema20=100.0,
        ema20_slope5=-0.02,
        return5=-0.05,
        return20=-0.1,
        macd_hist=-0.3,
    )

    result = rotation.classify_state(point, [])

    assert result.state == "inactive"


@pytest.mark.parametrize(
    ("point", "expected"),
    [
        (
            _point(
                flip="bearish",
                close=99.0,
                ema20=100.0,
                ema20_slope5=-0.01,
                macd_hist=0.1,
            ),
            "confirmed",
        ),
        (
            _point(
                close=100.0,
                ema5=98.0,
                ema10=99.0,
                ema20=101.0,
                return5=-0.03,
                macd_hist=-0.1,
            ),
            "mild",
        ),
        (
            _point(
                flip="bearish",
                close=95.0,
                ema20=100.0,
                macd_hist=-0.2,
                adx14=30.0,
            ),
            "severe",
        ),
    ],
)
def test_recent_active_trend_can_enter_each_fading_severity(point, expected):
    result = rotation.classify_state(point, _strong_history())

    assert result.state == "fading"
    assert result.severity == expected


@pytest.mark.parametrize(
    ("stage", "setup", "severity", "eligible", "expected"),
    [
        ("emerging", "confirmed", None, True, "rotate_in"),
        ("emerging", "confirmed", None, False, "watch"),
        ("emerging", "rebound", None, True, "watch"),
        ("strong", None, None, True, "hold"),
        ("fading", None, "mild", False, "reduce"),
        ("fading", None, "confirmed", False, "exit"),
        ("fading", None, "severe", False, "exit"),
    ],
)
def test_v2_action_mapping(stage, setup, severity, eligible, expected):
    assert (
        rotation.determine_action(
            stage,
            setup=setup,
            severity=severity,
            entry_eligible=eligible,
        )
        == expected
    )


def test_indicator_points_use_extended_talib_and_stockstats_ten_three():
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
    index = count - 1

    point = rotation._indicator_points(
        rotation._Series(symbol="510300.SH", name="ETF", frame=frame),
        range(index, index + 1),
    )[index]

    expected_return = frame.close.iloc[-1] / frame.close.iloc[-21] - 1
    assert point.metrics["return20"] == pytest.approx(expected_return)
    assert point.metrics["adx14"] > 0
    assert np.isfinite(point.metrics["macd_hist"])
    assert point.metrics["atr10"] > 0
    assert len(point.supertrend_direction) == count


def _empty_result() -> RotationResult:
    return RotationResult(
        sources=[],
        summary=RotationSummary(
            total=0,
            analyzed=0,
            failed=0,
            emerging=0,
            strong=0,
            fading=0,
            inactive=0,
        ),
    )


def test_v2_contract_exposes_three_arrays_and_inactive_count_only():
    payload = _empty_result().model_dump()

    assert payload["model"] == "rotation_v2"
    assert {"emerging", "strong", "fading"} <= payload.keys()
    assert "inactive" not in payload
    assert payload["summary"]["inactive"] == 0
    assert not ({"leading", "weakening", "lagging"} & payload.keys())


def test_route_calculates_before_replacing_three_targets(monkeypatch):
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
        strong="strong",
        fading="fading",
    )

    assert [call[0] for call in calls] == ["emerging", "strong", "fading"]
    assert all(call[2] == SecuritiesUpdateMode.Replace for call in calls)
    assert [target.stage for target in routed.targets] == ["emerging", "strong", "fading"]


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
            strong="strong",
            fading="fading",
        )
