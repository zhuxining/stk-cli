"""Regression tests for cross-platform watchlist sync."""

import sys
from types import SimpleNamespace

from stk.services import sync as sync_mod


def _ths_item(code: str, market: str) -> SimpleNamespace:
    return SimpleNamespace(code=code, market=market)


def _install_mocks(
    monkeypatch,
    *,
    ths_items: list[SimpleNamespace],
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

    def fake_add_symbols(name, symbols, mode=None):
        if add_raises:
            raise add_raises
        calls["added"].extend(symbols)

    monkeypatch.setitem(
        sys.modules,
        "stk.services.ths_wrapper",
        SimpleNamespace(get_ths_group=fake_get_ths_group),
    )
    monkeypatch.setitem(
        sys.modules,
        "stk.services.watchlist",
        SimpleNamespace(add_symbols=fake_add_symbols),
    )
    return calls


def test_pull_merge_adds_all_no_remove(monkeypatch):
    """Merge mode adds all THS stocks, never removes — even if LP already has them.

    THS returns 300001.CYB + 600519.SH; LP already has 300001.SZ + 600519.SH.
    Merge mode skips diff computation and adds all THS symbols directly
    (underlying API handles duplicates gracefully). No removes ever issued.
    """
    calls = _install_mocks(
        monkeypatch,
        ths_items=[_ths_item("300001", "CYB"), _ths_item("600519", "SH")],
    )

    result = sync_mod.pull_from_ths("ths_group", "lp_group")

    assert result.added == 2
    assert result.removed == 0
    assert calls["added"] == ["300001.SZ", "600519.SH"]
    assert calls["removed"] == []


def test_pull_adds_cyb_stock_with_correct_symbol(monkeypatch):
    """A 创业板 stock only on THS side is added as a valid .SZ symbol."""
    calls = _install_mocks(
        monkeypatch,
        ths_items=[_ths_item("300001", "CYB"), _ths_item("510300", "SHETF")],
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
    )

    result = sync_mod.pull_from_ths("ths_group", "lp_group")

    assert result.added == 1
    assert calls["added"] == ["300001.SZ"]
    assert "000001.ZS" not in calls["added"]
    assert "000012.ZQ" not in calls["added"]


def test_pull_replace_mode_uses_atomic_replace(monkeypatch):
    """--replace avoids intersection wipe by using mode=Replace, not add+remove."""
    from longport.openapi import SecuritiesUpdateMode

    calls = _install_mocks(
        monkeypatch,
        ths_items=[_ths_item("300001", "CYB"), _ths_item("600519", "SH")],
    )

    def capturing_add(name, symbols, mode=None):
        calls["mode"] = mode
        calls["added"].extend(symbols)

    # pull_from_ths lazily imports from sys.modules (mocked by _install_mocks)
    monkeypatch.setattr(sys.modules["stk.services.watchlist"], "add_symbols", capturing_add)
    result = sync_mod.pull_from_ths("ths_group", "lp_group", replace=True)

    assert result.added == 2
    assert calls["mode"] is SecuritiesUpdateMode.Replace
    assert calls["added"] == ["300001.SZ", "600519.SH"]


def test_pull_surfaces_add_failure(monkeypatch):
    """A failed add is reported in errors without crashing the sync.

    With add-before-remove ordering, an add failure no longer leaves the group
    half-cleared by a prior remove; the error is collected and returned.
    """
    _install_mocks(
        monkeypatch,
        ths_items=[_ths_item("300001", "CYB")],
        add_raises=RuntimeError("boom"),
    )

    result = sync_mod.pull_from_ths("ths_group", "lp_group")

    assert result.errors
    assert any("添加失败" in e for e in result.errors)
