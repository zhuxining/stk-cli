"""Tests for the public CLI command tree."""

from types import SimpleNamespace

from typer.main import get_command
from typer.testing import CliRunner

from stk.cli import app
from stk.models.indicator import DailyResult
from stk.models.watchlist import WorkflowResult

runner = CliRunner()


def test_root_exposes_only_core_routes():
    command = get_command(app)

    assert set(command.commands) == {"data", "group", "scan"}


def test_group_exposes_platforms_sync_and_route():
    result = runner.invoke(app, ["group", "--help"])

    assert result.exit_code == 0
    assert "longport" in result.stdout
    assert "ths" in result.stdout
    assert "sync" in result.stdout
    assert "route" in result.stdout


def test_sync_has_no_ambiguous_list_command():
    result = runner.invoke(app, ["group", "sync", "--help"])

    assert result.exit_code == 0
    assert "diff" in result.stdout
    assert "push" in result.stdout
    assert "pull" in result.stdout
    assert "list" not in result.stdout


def test_data_kline_expands_symbols(monkeypatch):
    calls: list[str] = []

    def fake_get_daily(symbol: str, *, period: str, count: int) -> DailyResult:
        calls.append(symbol)
        return DailyResult(symbol=symbol, days=[])

    monkeypatch.setattr("stk.services.indicator.get_daily", fake_get_daily)

    result = runner.invoke(app, ["data", "kline", "600519,000001", "700.HK"])

    assert result.exit_code == 0
    assert calls == ["600519", "000001", "700.HK"]


def test_group_route_delegates_to_service(monkeypatch):
    calls: list[tuple[str, str, str, bool]] = []

    def fake_route(src: str, entry: str, exit_: str, *, replace: bool) -> WorkflowResult:
        calls.append((src, entry, exit_, replace))
        return WorkflowResult(action="route")

    monkeypatch.setattr("stk.services.watchlist.route_signals", fake_route)

    result = runner.invoke(app, ["group", "route", "source", "entry", "exit", "--replace"])

    assert result.exit_code == 0
    assert calls == [("source", "entry", "exit", True)]


def test_group_route_rejects_shared_destination():
    result = runner.invoke(app, ["group", "route", "source", "same", "same"])

    assert result.exit_code != 0
    assert isinstance(result.exception, Exception)


def test_scan_delegates_to_longport_group(monkeypatch):
    calls: list[tuple[str, bool, bool]] = []

    def fake_scan(
        name: str,
        *,
        include_daily10: bool,
        include_full_context: bool,
    ) -> SimpleNamespace:
        calls.append((name, include_daily10, include_full_context))
        return SimpleNamespace(result="ok")

    monkeypatch.setattr("stk.services.scan.scan_watchlist", fake_scan)

    result = runner.invoke(app, ["scan", "focus", "--daily10", "--full-context"])

    assert result.exit_code == 0
    assert calls == [("focus", True, True)]
