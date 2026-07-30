"""Tests for Longport signal routing."""

from types import SimpleNamespace

from longport.openapi import SecuritiesUpdateMode
import pytest

from stk.errors import SourceError
from stk.models.scan import MonitorSummary, ScanError
from stk.models.watchlist import Watchlist
from stk.services import watchlist as watchlist_service


def _scan_result(
    buy: list[str],
    *,
    sell: list[str] | None = None,
    errors: list[ScanError] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        focus=[SimpleNamespace(symbol=symbol) for symbol in buy],
        risk=[SimpleNamespace(symbol=symbol) for symbol in sell or []],
        summary=MonitorSummary(
            focus_count=len(buy),
            recommend_count=len(buy),
            entry_signal_count=len(buy),
            exit_signal_count=len(sell or []),
            watch_signal_count=0,
        ),
        errors=errors or [],
    )


def test_route_replaces_current_buy_and_sell_snapshots(monkeypatch):
    calls: list[tuple[str, list[str], object]] = []
    monkeypatch.setattr(
        "stk.services.scan.scan_watchlist",
        lambda *args, **kwargs: _scan_result(
            ["600519.SH"],
            sell=["000001.SZ"],
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
        ("entry", ["600519.SH"], SecuritiesUpdateMode.Replace),
        ("exit", ["000001.SZ"], SecuritiesUpdateMode.Replace),
    ]
    assert result.buy == ["600519.SH"]
    assert result.sell == ["000001.SZ"]
    assert [group.name for group in result.destinations] == ["entry", "exit"]


def test_route_aborts_without_modifying_groups_when_scan_fails(monkeypatch):
    calls: list[tuple[str, list[str], object]] = []
    monkeypatch.setattr(
        "stk.services.scan.scan_watchlist",
        lambda *args, **kwargs: _scan_result(
            [],
            errors=[ScanError(symbol="600519.SH", reason="history unavailable")],
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

    with pytest.raises(SourceError, match="signal groups were not modified"):
        watchlist_service.route_signals("source", "entry", "exit")

    assert calls == []
