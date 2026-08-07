"""Tests for ths_wrapper resilience against intermittent empty responses."""

from types import SimpleNamespace

import pytest
import requests

from stk.errors import SourceError
from stk.services import ths_wrapper


class _FakeApi:
    def __init__(self) -> None:
        self._client = SimpleNamespace(get_cookies=lambda: {})


def _patch_sleep(monkeypatch, delays: list[float]) -> None:
    """Replace time.sleep with a no-op that records requested delays."""
    recorded: list[float] = []

    def fake_sleep(seconds: float) -> None:
        recorded.append(seconds)

    monkeypatch.setattr(ths_wrapper.time, "sleep", fake_sleep)
    return recorded


def test_dynamic_plate_retries_and_converts_to_ths_error(monkeypatch):
    """JSONDecodeError from a 204/empty response must become THSNetworkError."""
    import api as ths_api
    from exceptions import THSNetworkError

    calls: list[str] = []

    def fake_query(group_name, cookies, **kwargs):
        calls.append(group_name)
        raise requests.exceptions.JSONDecodeError("Expecting value", "", 0)

    monkeypatch.setattr(ths_api, "_query_dynamic_plate", fake_query)
    _patch_sleep(monkeypatch, [])

    method = ths_api.FavoriteAPI.query_dynamic_plate
    with pytest.raises(THSNetworkError, match="动态板块"):
        method(_FakeApi(), "竞价抢筹")

    # retried 3 times with backoff before giving up
    assert calls == ["竞价抢筹"] * 3


def test_dynamic_plate_recovers_on_retry(monkeypatch):
    """An intermittent failure should not abort the whole group fetch."""
    import api as ths_api

    calls: list[str] = []
    items = [SimpleNamespace(code="600519", market_type="SH")]

    def flaky_query(group_name, cookies, **kwargs):
        calls.append(group_name)
        if len(calls) == 1:
            raise requests.exceptions.JSONDecodeError("Expecting value", "", 0)
        return items

    monkeypatch.setattr(ths_api, "_query_dynamic_plate", flaky_query)
    _patch_sleep(monkeypatch, [])

    method = ths_api.FavoriteAPI.query_dynamic_plate
    assert method(_FakeApi(), "冲刺涨停") == items
    assert len(calls) == 2


def test_dynamic_plate_success_passthrough(monkeypatch):
    """Healthy dynamic-plate responses pass through unchanged."""
    import api as ths_api

    items = [SimpleNamespace(code="000021", market_type="SZ")]
    monkeypatch.setattr(ths_api, "_query_dynamic_plate", lambda g, c, **kw: items)

    method = ths_api.FavoriteAPI.query_dynamic_plate
    assert method(_FakeApi(), "主题ETF") == items


def test_portfolio_converts_request_exception(monkeypatch):
    """Any RequestException escaping the portfolio body becomes SourceError."""
    import service as ths_service

    monkeypatch.setattr(ths_wrapper.settings, "ths_username", "user")
    monkeypatch.setattr(ths_wrapper.settings, "ths_password", "pass")

    class _FakePM:
        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

    monkeypatch.setattr(ths_service, "PortfolioManager", lambda **kwargs: _FakePM())

    with pytest.raises(SourceError, match="同花顺接口响应异常"):
        with ths_wrapper.get_ths_portfolio():
            raise requests.exceptions.ConnectionError("boom")


def test_portfolio_converts_ths_error(monkeypatch):
    """Upstream THSError inside the portfolio body becomes SourceError."""
    from exceptions import THSError
    import service as ths_service

    monkeypatch.setattr(ths_wrapper.settings, "ths_username", "user")
    monkeypatch.setattr(ths_wrapper.settings, "ths_password", "pass")

    class _FakePM:
        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

    monkeypatch.setattr(ths_service, "PortfolioManager", lambda **kwargs: _FakePM())

    with pytest.raises(SourceError, match="同花顺 API 错误"), ths_wrapper.get_ths_portfolio():
        raise THSError("业务失败")
