"""Tests for the Xueqiu API adapter."""

from types import SimpleNamespace

import pytest
import requests

from stk.config import settings
from stk.errors import SourceError
from stk.services.xueqiu import XueqiuClient


class FakeSession:
    def __init__(self, handler):
        self.handler = handler
        self.cookies = requests.cookies.RequestsCookieJar()
        self.headers: dict[str, str] = {}
        self.calls: list[tuple[str, str, dict]] = []

    def request(self, method, url, timeout, **kwargs):
        self.calls.append((method, url, kwargs))
        payload = self.handler(method, url, kwargs)
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: payload)


@pytest.fixture(autouse=True)
def xueqiu_settings(monkeypatch):
    monkeypatch.setattr(settings, "xueqiu_uid", "123")
    monkeypatch.setattr(settings, "xueqiu_a_token", "a-token")
    monkeypatch.setattr(settings, "xueqiu_id_token", "id-token")


def _groups(*items):
    return {"error_code": 0, "data": {"stocks": list(items)}}


def _stocks(*items):
    return {"error_code": 0, "data": {"stocks": list(items)}}


def test_client_uses_three_cookies_and_resolves_default_alias():
    def handler(_method, url, _kwargs):
        if url.endswith("/portfolio/list.json"):
            return _groups(
                {"id": -1, "name": "全部", "symbol_count": 1, "type": -1},
                {"id": -5, "name": "沪深", "symbol_count": 1, "type": -1},
            )
        return _stocks({"symbol": "SZ002364", "exchange": "SZ", "name": "中恒电气"})

    session = FakeSession(handler)
    result = XueqiuClient(session).get_watchlist()

    assert session.cookies.get_dict() == {
        "u": "123",
        "xq_a_token": "a-token",
        "xq_id_token": "id-token",
    }
    assert result.name == "我的自选"
    assert result.securities[0].symbol == "SZ002364"
    assert session.calls[1][2]["params"]["pid"] == "-1"


def test_custom_membership_changes_preserve_other_groups():
    modified: list[dict] = []

    def handler(method, url, kwargs):
        if url.endswith("/portfolio/list.json"):
            return _groups(
                {"id": 0, "name": "目标", "symbol_count": 0, "type": 1},
                {"id": 1, "name": "保留", "symbol_count": 1, "type": 1},
            )
        if url.endswith("/stock/list.json"):
            if kwargs["params"]["pid"] == "1":
                return _stocks({"symbol": "SH600519", "exchange": "SH"})
            return _stocks()
        if method == "POST" and url.endswith("/modify_portfolio.json"):
            modified.append(kwargs["data"])
            return {"error_code": 0, "data": True}
        raise AssertionError((method, url, kwargs))

    client = XueqiuClient(FakeSession(handler))
    client.add_stocks("目标", ["SH600519"])
    client.remove_stocks("目标", ["SH600519"])

    assert modified == [
        {"symbols": "SH600519", "pnames": "保留,目标", "category": 1},
        {"symbols": "SH600519", "pnames": "保留", "category": 1},
    ]


def test_default_group_uses_v5_add_and_cancel():
    calls: list[tuple[str, dict]] = []

    def handler(method, url, kwargs):
        if method == "GET":
            return _groups({"id": -1, "name": "全部", "symbol_count": 0, "type": -1})
        calls.append((url, kwargs["data"]))
        return {"error_code": 0, "data": True}

    client = XueqiuClient(FakeSession(handler))
    client.add_stocks("我的自选", ["SH600519"])
    client.remove_stocks("我的自选", ["SH600519"])

    assert calls[0][0].endswith("/stock/add.json")
    assert calls[0][1] == {"symbols": "SH600519"}
    assert calls[1][0].endswith("/stock/cancel.json")


def test_client_surfaces_api_error_without_credentials():
    session = FakeSession(
        lambda _method, _url, _kwargs: {
            "error_code": 400016,
            "error_description": "登录已过期",
        }
    )

    with pytest.raises(SourceError, match="登录已过期") as raised:
        XueqiuClient(session).list_groups()

    assert "a-token" not in str(raised.value)
