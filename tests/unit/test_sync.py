"""Regression tests for cross-platform watchlist sync.

Guards against the bug where pull/push cleared the target group but failed to
sync THS content: THS returns CYB/SHETF/SZETF market abbrs, but the converter
only handled CY/KC, so 创业板/ETF symbols round-tripped to invalid longport
symbols. Combined with remove-before-add, this silently wiped groups.
"""

import sys
from types import SimpleNamespace

from stk.models.watchlist import Watchlist, WatchlistSecurity
from stk.services import sync as sync_mod


def _ths_item(code: str, market: str) -> SimpleNamespace:
    return SimpleNamespace(code=code, market=market)


def _watchlist(name: str, symbols: list[str]) -> Watchlist:
    return Watchlist(
        id=1,
        name=name,
        securities=[WatchlistSecurity(symbol=s) for s in symbols],
    )


def _install_mocks(
    monkeypatch,
    *,
    ths_items: list[SimpleNamespace],
    lp_symbols: list[str],
    lp_exists: bool = True,
    add_raises: Exception | None = None,
) -> dict:
    """Install fakes for ths_wrapper + watchlist used by pull_from_ths.

    pull_from_ths imports its dependencies lazily inside the function body, so
    we patch sys.modules entries rather than module attributes.
    """
    calls: dict[str, list] = {"added": [], "removed": []}

    def fake_get_ths_group(name):
        return {
            "name": name,
            "group_id": "g1",
            "items": ths_items,
            "readonly": False,
        }

    def fake_get_watchlist(name):
        if not lp_exists:
            raise RuntimeError("not found")
        return _watchlist(name, lp_symbols)

    def fake_add_symbols(name, symbols, mode=None):
        if add_raises:
            raise add_raises
        calls["added"].extend(symbols)

    def fake_remove_symbols(name, symbols):
        calls["removed"].extend(symbols)

    monkeypatch.setattr(sync_mod, "get_ths_group", fake_get_ths_group, raising=False)
    monkeypatch.setitem(
        sys.modules,
        "stk.services.ths_wrapper",
        SimpleNamespace(get_ths_group=fake_get_ths_group),
    )
    monkeypatch.setitem(
        sys.modules,
        "stk.services.watchlist",
        SimpleNamespace(
            get_watchlist=fake_get_watchlist,
            create_group=lambda name: _watchlist(name, []),
            add_symbols=fake_add_symbols,
            remove_symbols=fake_remove_symbols,
        ),
    )
    return calls


def test_pull_cyb_round_trips_no_spurious_remove(monkeypatch):
    """创业板 stock already present on both sides must be unchanged.

    Before fix: THS returns 300001.CYB, longport has 300001.SZ; converter failed
    to map CYB→SZ, so the same stock was both removed (as 300001.SZ) and added
    (as the invalid 300001.CYB). The remove succeeded, the add failed → group
    wiped. Now CYB maps back to .SZ and the diff is empty.
    """
    calls = _install_mocks(
        monkeypatch,
        ths_items=[_ths_item("300001", "CYB"), _ths_item("600519", "SH")],
        lp_symbols=["300001.SZ", "600519.SH"],
    )

    result = sync_mod.pull_from_ths("ths_group", "lp_group")

    assert result.added == 0
    assert result.removed == 0
    assert result.diff.unchanged == 2
    assert calls["added"] == []
    assert calls["removed"] == []


def test_pull_adds_cyb_stock_with_correct_symbol(monkeypatch):
    """A 创业板 stock only on THS side is added as a valid .SZ symbol."""
    calls = _install_mocks(
        monkeypatch,
        ths_items=[_ths_item("300001", "CYB"), _ths_item("510300", "SHETF")],
        lp_symbols=[],
    )

    result = sync_mod.pull_from_ths("ths_group", "lp_group")

    assert result.added == 2
    assert calls["added"] == ["300001.SZ", "510300.SH"]
    assert calls["removed"] == []


def test_pull_drops_unsupported_ths_assets(monkeypatch):
    """THS indices/funds are dropped before the longport batch call."""
    calls = _install_mocks(
        monkeypatch,
        ths_items=[
            _ths_item("300001", "CYB"),
            _ths_item("000001", "ZS"),  # 上证指数
            _ths_item("000012", "ZQ"),  # 债券
        ],
        lp_symbols=[],
    )

    result = sync_mod.pull_from_ths("ths_group", "lp_group")

    assert result.added == 1
    assert calls["added"] == ["300001.SZ"]
    assert "000001.ZS" not in calls["added"]
    assert "000012.ZQ" not in calls["added"]


def test_pull_surfaces_add_failure(monkeypatch):
    """A failed add is reported in errors without crashing the sync.

    With add-before-remove ordering, an add failure no longer leaves the group
    half-cleared by a prior remove; the error is collected and returned.
    """
    _install_mocks(
        monkeypatch,
        ths_items=[_ths_item("300001", "CYB")],
        lp_symbols=["600519.SH"],
        add_raises=RuntimeError("boom"),
    )

    result = sync_mod.pull_from_ths("ths_group", "lp_group")

    assert result.errors
    assert any("添加失败" in e for e in result.errors)
