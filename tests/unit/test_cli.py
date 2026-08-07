"""Tests for the public CLI command tree and new options."""

import json

from typer.main import get_command
from typer.testing import CliRunner

from stk.cli import app
from stk.models.indicator import KlineSeries
from stk.models.rotation import RotationRouteResult, RotationSummary
from stk.models.scan import ScanResult, ScanSummary
from stk.models.watchlist import RouteResult, RouteSource, RouteTarget, RouteTargets

runner = CliRunner()


def test_root_exposes_only_core_routes():
    assert set(get_command(app).commands) == {"data", "group", "rotate", "scan"}


def test_group_exposes_platforms_sync_and_route():
    result = runner.invoke(app, ["group", "--help"])

    assert result.exit_code == 0
    for command in ("longport", "ths", "xueqiu", "sync", "route", "rotate"):
        assert command in result.stdout


def test_data_kline_returns_partial_success(monkeypatch):
    def fake_get_daily(symbol: str, *, period: str, count: int) -> KlineSeries:
        if symbol == "bad":
            raise RuntimeError("boom")
        return KlineSeries(symbol=f"{symbol}.SH", bars=[])

    monkeypatch.setattr("stk.services.indicator.get_daily", fake_get_daily)

    result = runner.invoke(app, ["data", "kline", "600519", "bad"])
    payload = json.loads(result.stdout)

    assert result.exit_code == 0
    assert payload["ok"] is True
    assert payload["status"] == "partial"
    assert payload["data"]["requested"] == 2
    assert payload["data"]["series"][0]["symbol"] == "600519.SH"
    assert payload["data"]["failures"][0]["code"] == "runtime_error"


def test_group_route_delegates_three_positional_targets(monkeypatch):
    calls: list[tuple[str, str, str, str, bool]] = []

    def fake_route(
        group: str,
        buy: str,
        sell: str,
        hold: str,
        *,
        replace: bool = True,
    ) -> RouteResult:
        calls.append((group, buy, sell, hold, replace))
        return RouteResult(
            mode="replace",
            source=RouteSource(group=group, total=0, analyzed=0, failed=0),
            targets=RouteTargets(
                buy=RouteTarget(group=buy),
                hold=RouteTarget(group=hold),
                sell=RouteTarget(group=sell),
            ),
        )

    monkeypatch.setattr("stk.services.watchlist.route_signals", fake_route)

    result = runner.invoke(
        app,
        ["group", "route", "source", "buy", "sell", "hold"],
    )

    assert result.exit_code == 0
    assert calls == [("source", "buy", "sell", "hold", True)]


def test_group_rotate_uses_three_v2_targets(monkeypatch):
    calls: list[tuple[list[str], str, str, str]] = []

    def fake_rotate(
        sources: list[str], *, emerging: str, strong: str, fading: str
    ) -> RotationRouteResult:
        calls.append((sources, emerging, strong, fading))
        return RotationRouteResult(
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
            targets=[],
        )

    monkeypatch.setattr("stk.services.rotation.route_rotation", fake_rotate)

    result = runner.invoke(
        app,
        [
            "group",
            "rotate",
            "--source",
            "theme",
            "--emerging",
            "start",
            "--strong",
            "strong",
            "--fading",
            "fade",
        ],
    )

    assert result.exit_code == 0
    assert calls == [(["theme"], "start", "strong", "fade")]


def test_group_rotate_rejects_v1_target_options():
    result = runner.invoke(
        app,
        ["group", "rotate", "--source", "theme", "--leading", "leading"],
    )

    assert result.exit_code != 0


def test_scan_uses_new_detail_options(monkeypatch):
    calls: list[tuple[str, int, bool]] = []

    def fake_scan(name: str, *, recent_bars: int, include_factors: bool) -> ScanResult:
        calls.append((name, recent_bars, include_factors))
        return ScanResult(
            group=name,
            summary=ScanSummary(
                total=0,
                analyzed=0,
                failed=0,
                buy=0,
                sell=0,
                watch=0,
                ignored=0,
            ),
        )

    monkeypatch.setattr("stk.services.scan.scan_watchlist", fake_scan)

    result = runner.invoke(
        app,
        ["scan", "core", "--recent-bars", "5", "--include-factors"],
    )

    assert result.exit_code == 0
    assert calls == [("core", 5, True)]


def test_scan_rejects_removed_options():
    result = runner.invoke(app, ["scan", "core", "--daily10"])

    assert result.exit_code != 0
