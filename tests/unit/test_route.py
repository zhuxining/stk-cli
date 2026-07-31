"""Tests for Longport signal snapshot routing."""

from types import SimpleNamespace

from longport.openapi import SecuritiesUpdateMode
import pytest

from stk.models.common import BatchFailure
from stk.models.scan import ScanSummary
from stk.services import watchlist as watchlist_service


def _scan_result(
    buy: list[str],
    *,
    sell: list[str] | None = None,
    failures: list[BatchFailure] | None = None,
) -> SimpleNamespace:
    sell = sell or []
    failures = failures or []
    return SimpleNamespace(
        buy=[SimpleNamespace(symbol=symbol) for symbol in buy],
        sell=[SimpleNamespace(symbol=symbol) for symbol in sell],
        summary=ScanSummary(
            total=len(buy) + len(sell) + len(failures),
            analyzed=len(buy) + len(sell),
            failed=len(failures),
            buy=len(buy),
            sell=len(sell),
            watch=0,
            ignored=0,
        ),
        failures=failures,
    )


def test_route_replaces_snapshots_without_refetching_targets(monkeypatch):
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
        lambda name: pytest.fail("route must not refetch destination groups"),
    )

    result = watchlist_service.route_signals("source", "buy", "sell")

    assert calls == [
        ("buy", ["600519.SH"], SecuritiesUpdateMode.Replace),
        ("sell", ["000001.SZ"], SecuritiesUpdateMode.Replace),
    ]
    assert result.mode == "replace"
    assert result.source.failed == 0
    assert result.targets.buy.symbols == ["600519.SH"]
    assert result.targets.sell.symbols == ["000001.SZ"]
    assert result.failures == []


def test_route_updates_snapshots_and_reports_scan_failures(monkeypatch):
    calls: list[tuple[str, list[str], object]] = []
    failure = BatchFailure(
        symbol="600519.SH",
        code="source_error",
        message="history unavailable",
    )
    monkeypatch.setattr(
        "stk.services.scan.scan_watchlist",
        lambda *args, **kwargs: _scan_result(
            ["000001.SZ"],
            failures=[failure],
        ),
    )
    monkeypatch.setattr(
        watchlist_service,
        "add_symbols",
        lambda name, symbols, mode: calls.append((name, symbols, mode)),
    )

    result = watchlist_service.route_signals("source", "buy", "sell")

    assert calls == [
        ("buy", ["000001.SZ"], SecuritiesUpdateMode.Replace),
        ("sell", [], SecuritiesUpdateMode.Replace),
    ]
    assert result.source.total == 2
    assert result.source.analyzed == 1
    assert result.source.failed == 1
    assert result.failures == [failure]
