"""Tests for Longport signal routing."""

from types import SimpleNamespace

from longport.openapi import SecuritiesUpdateMode

from stk.models.scan import MonitorSummary
from stk.models.watchlist import Watchlist
from stk.services import watchlist as watchlist_service


def _scan_result(signals: list[tuple[str, str]]) -> SimpleNamespace:
    return SimpleNamespace(
        focus=[
            SimpleNamespace(symbol=symbol, decision=SimpleNamespace(signal=signal))
            for symbol, signal in signals
        ],
        summary=MonitorSummary(
            focus_count=len(signals),
            recommend_count=len(signals),
            entry_signal_count=sum(signal != "趋势退出" for _, signal in signals),
            exit_signal_count=sum(signal == "趋势退出" for _, signal in signals),
            watch_signal_count=0,
        ),
    )


def test_route_appends_entry_and_exit_signals(monkeypatch):
    calls: list[tuple[str, list[str], object]] = []
    monkeypatch.setattr(
        "stk.services.scan.scan_watchlist",
        lambda *args, **kwargs: _scan_result(
            [("600519.SH", "趋势买入"), ("000001.SZ", "趋势退出")]
        ),
    )
    monkeypatch.setattr(
        watchlist_service,
        "add_symbols",
        lambda name, symbols, mode: calls.append((name, symbols, mode)),
    )
    monkeypatch.setattr(
        watchlist_service,
        "get_watchlist",
        lambda name: Watchlist(id=1, name=name),
    )

    result = watchlist_service.route_signals("source", "entry", "exit")

    assert calls == [
        ("entry", ["600519.SH"], SecuritiesUpdateMode.Add),
        ("exit", ["000001.SZ"], SecuritiesUpdateMode.Add),
    ]
    assert [group.name for group in result.destinations] == ["entry", "exit"]


def test_route_replace_clears_empty_destination(monkeypatch):
    calls: list[tuple[str, list[str], object]] = []
    monkeypatch.setattr(
        "stk.services.scan.scan_watchlist",
        lambda *args, **kwargs: _scan_result([("600519.SH", "趋势买入")]),
    )
    monkeypatch.setattr(
        watchlist_service,
        "add_symbols",
        lambda name, symbols, mode: calls.append((name, symbols, mode)),
    )
    monkeypatch.setattr(
        watchlist_service,
        "get_watchlist",
        lambda name: Watchlist(id=1, name=name),
    )

    watchlist_service.route_signals("source", "entry", "exit", replace=True)

    assert calls == [
        ("entry", ["600519.SH"], SecuritiesUpdateMode.Replace),
        ("exit", [], SecuritiesUpdateMode.Replace),
    ]
