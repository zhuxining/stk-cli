"""Regression tests for cross-platform group synchronization."""

import sys
from types import SimpleNamespace

from stk.errors import SourceError
from stk.services import sync as sync_mod


def _ths_item(code: str, market: str) -> SimpleNamespace:
    return SimpleNamespace(code=code, market=market)


def _install_pull_mocks(
    monkeypatch,
    *,
    ths_items: list[SimpleNamespace],
    target_symbols: list[str] | None = None,
    add_raises: Exception | None = None,
) -> dict:
    calls: dict[str, object] = {"added": [], "mode": None}

    def get_ths_group(name):
        return {
            "name": name,
            "group_id": "g1",
            "items": ths_items,
            "readonly": False,
        }

    def get_watchlist(name):
        if target_symbols is None:
            raise SourceError("missing")
        return SimpleNamespace(
            securities=[SimpleNamespace(symbol=symbol) for symbol in target_symbols]
        )

    def add_symbols(name, symbols, mode=None):
        if add_raises:
            raise add_raises
        calls["added"] = symbols
        calls["mode"] = mode

    monkeypatch.setitem(
        sys.modules,
        "stk.services.ths_wrapper",
        SimpleNamespace(get_ths_group=get_ths_group),
    )
    monkeypatch.setitem(
        sys.modules,
        "stk.services.watchlist",
        SimpleNamespace(add_symbols=add_symbols, get_watchlist=get_watchlist),
    )
    return calls


def test_pull_merge_only_adds_missing_symbols(monkeypatch):
    calls = _install_pull_mocks(
        monkeypatch,
        ths_items=[_ths_item("300001", "CYB"), _ths_item("600519", "SH")],
        target_symbols=["600519.SH"],
    )

    result = sync_mod.pull_from_ths("ths_group", "lp_group")

    assert calls["added"] == ["300001.SZ"]
    assert result.changes.add_symbols == ["300001.SZ"]
    assert result.changes.unchanged_count == 1
    assert result.applied is not None
    assert result.applied.added_count == 1


def test_pull_drops_unsupported_assets(monkeypatch):
    calls = _install_pull_mocks(
        monkeypatch,
        ths_items=[
            _ths_item("300001", "CYB"),
            _ths_item("000001", "ZS"),
            _ths_item("000012", "ZQ"),
        ],
    )

    result = sync_mod.pull_from_ths("ths_group", "lp_group")

    assert calls["added"] == ["300001.SZ"]
    assert result.changes.add_symbols == ["300001.SZ"]


def test_pull_replace_uses_atomic_replace_and_reports_removals(monkeypatch):
    from longport.openapi import SecuritiesUpdateMode

    calls = _install_pull_mocks(
        monkeypatch,
        ths_items=[_ths_item("300001", "CYB")],
        target_symbols=["600519.SH"],
    )

    result = sync_mod.pull_from_ths("ths_group", "lp_group", replace=True)

    assert calls["mode"] is SecuritiesUpdateMode.Replace
    assert calls["added"] == ["300001.SZ"]
    assert result.changes.remove_symbols == ["600519.SH"]
    assert result.applied is not None
    assert result.applied.removed_count == 1


def test_pull_surfaces_structured_failure(monkeypatch):
    _install_pull_mocks(
        monkeypatch,
        ths_items=[_ths_item("300001", "CYB")],
        add_raises=RuntimeError("boom"),
    )

    result = sync_mod.pull_from_ths("ths_group", "lp_group")

    assert result.failures[0].operation == "add"
    assert result.failures[0].code == "runtime_error"
    assert result.failures[0].message == "boom"


def test_xueqiu_push_replace_skips_removals_when_add_fails(monkeypatch):
    removed: list[str] = []

    monkeypatch.setitem(
        sys.modules,
        "stk.services.watchlist",
        SimpleNamespace(
            get_watchlist=lambda _name: SimpleNamespace(
                securities=[SimpleNamespace(symbol="600519.SH")]
            )
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "stk.services.xueqiu",
        SimpleNamespace(
            XueqiuClient=lambda: SimpleNamespace(
                get_watchlist=lambda _name: SimpleNamespace(
                    securities=[SimpleNamespace(symbol="SZ000001", market="SZ")]
                ),
                add_stocks=lambda _name, _symbols: (_ for _ in ()).throw(RuntimeError("boom")),
                remove_stocks=lambda _name, symbols: removed.extend(symbols),
            ),
        ),
    )

    result = sync_mod.push_to_xueqiu("lp", "我的自选", replace=True)

    assert result.changes.add_symbols == ["SH600519"]
    assert result.changes.remove_symbols == ["SZ000001"]
    assert result.failures[0].operation == "add"
    assert removed == []
