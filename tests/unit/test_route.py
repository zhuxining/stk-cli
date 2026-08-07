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
    hold: list[str] | None = None,
    failures: list[BatchFailure] | None = None,
) -> SimpleNamespace:
    sell = sell or []
    hold = hold or []
    failures = failures or []
    return SimpleNamespace(
        buy=[SimpleNamespace(symbol=symbol) for symbol in buy],
        hold=[SimpleNamespace(symbol=symbol) for symbol in hold],
        sell=[SimpleNamespace(symbol=symbol) for symbol in sell],
        summary=ScanSummary(
            total=len(buy) + len(sell) + len(hold) + len(failures),
            analyzed=len(buy) + len(sell) + len(hold),
            failed=len(failures),
            buy=len(buy),
            sell=len(sell),
            watch=0,
            hold=len(hold),
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
    monkeypatch.setattr(
        watchlist_service,
        "get_watchlist",
        lambda name: SimpleNamespace(
            securities=[
                SimpleNamespace(symbol=symbol)
                for symbol in {"buy": ["600519.SH"], "sell": []}[name]
            ]
        ),
    )

    result = watchlist_service.route_signals("source", "buy", "sell")

    # 600519.SH failed to scan but was already in the buy snapshot, so it is
    # preserved instead of being silently dropped by Replace.
    assert calls == [
        ("buy", ["000001.SZ", "600519.SH"], SecuritiesUpdateMode.Replace),
        ("sell", [], SecuritiesUpdateMode.Replace),
    ]
    assert result.targets.buy.symbols == ["000001.SZ", "600519.SH"]
    assert result.targets.sell.symbols == []
    assert result.source.total == 2
    assert result.source.analyzed == 1
    assert result.source.failed == 1
    assert result.failures == [failure]


def test_route_preserves_failed_members_in_both_destination_groups(monkeypatch):
    """Failed symbols are kept per destination group where they already exist."""
    calls: list[tuple[str, list[str], object]] = []
    failure = BatchFailure(symbol="000858.SZ", code="source_error", message="boom")
    monkeypatch.setattr(
        "stk.services.scan.scan_watchlist",
        lambda *args, **kwargs: _scan_result([], failures=[failure]),
    )
    monkeypatch.setattr(
        watchlist_service,
        "add_symbols",
        lambda name, symbols, mode: calls.append((name, symbols, mode)),
    )
    monkeypatch.setattr(
        watchlist_service,
        "get_watchlist",
        lambda name: SimpleNamespace(
            securities=[
                SimpleNamespace(symbol=symbol)
                for symbol in {"buy": ["000858.SZ"], "sell": ["000858.SZ"]}[name]
            ]
        ),
    )

    result = watchlist_service.route_signals("source", "buy", "sell")

    assert calls == [
        ("buy", ["000858.SZ"], SecuritiesUpdateMode.Replace),
        ("sell", ["000858.SZ"], SecuritiesUpdateMode.Replace),
    ]
    assert result.targets.buy.symbols == ["000858.SZ"]
    assert result.targets.sell.symbols == ["000858.SZ"]


def test_route_append_mode_never_refetches_destination_groups(monkeypatch):
    """Append mode does not preserve failures and must not read targets."""
    calls: list[tuple[str, list[str], object]] = []
    failure = BatchFailure(symbol="600519.SH", code="source_error", message="boom")
    monkeypatch.setattr(
        "stk.services.scan.scan_watchlist",
        lambda *args, **kwargs: _scan_result(
            ["600519.SH"],
            sell=["000001.SZ"],
            failures=[failure],
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
        lambda name: pytest.fail("append mode must not read destination groups"),
    )

    result = watchlist_service.route_signals("source", "buy", "sell", replace=False)

    assert calls == [
        ("buy", ["600519.SH"], SecuritiesUpdateMode.Add),
        ("sell", ["000001.SZ"], SecuritiesUpdateMode.Add),
    ]
    assert result.mode == "append"
    assert result.targets.hold is None


def test_route_writes_hold_snapshot_when_hold_group_provided(monkeypatch):
    calls: list[tuple[str, list[str], object]] = []
    monkeypatch.setattr(
        "stk.services.scan.scan_watchlist",
        lambda *args, **kwargs: _scan_result(
            ["600519.SH"],
            hold=["510300.SH"],
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
        lambda name: SimpleNamespace(securities=[]),
    )

    result = watchlist_service.route_signals("source", "buy", "sell", hold_dst="hold")

    assert calls == [
        ("buy", ["600519.SH"], SecuritiesUpdateMode.Replace),
        ("hold", ["510300.SH"], SecuritiesUpdateMode.Replace),
        ("sell", ["000001.SZ"], SecuritiesUpdateMode.Replace),
    ]
    assert result.targets.hold is not None
    assert result.targets.hold.group == "hold"
    assert result.targets.hold.symbols == ["510300.SH"]


def test_route_preserves_failed_hold_members(monkeypatch):
    """Failed symbols already in the hold group are preserved on Replace."""
    calls: list[tuple[str, list[str], object]] = []
    failure = BatchFailure(symbol="510300.SH", code="source_error", message="boom")
    monkeypatch.setattr(
        "stk.services.scan.scan_watchlist",
        lambda *args, **kwargs: _scan_result([], failures=[failure]),
    )
    monkeypatch.setattr(
        watchlist_service,
        "add_symbols",
        lambda name, symbols, mode: calls.append((name, symbols, mode)),
    )
    monkeypatch.setattr(
        watchlist_service,
        "get_watchlist",
        lambda name: SimpleNamespace(
            securities=[
                SimpleNamespace(symbol=symbol)
                for symbol in {"buy": [], "hold": ["510300.SH"], "sell": []}[name]
            ]
        ),
    )

    result = watchlist_service.route_signals("source", "buy", "sell", hold_dst="hold")

    assert calls == [
        ("buy", [], SecuritiesUpdateMode.Replace),
        ("hold", ["510300.SH"], SecuritiesUpdateMode.Replace),
        ("sell", [], SecuritiesUpdateMode.Replace),
    ]
    assert result.targets.hold.symbols == ["510300.SH"]
