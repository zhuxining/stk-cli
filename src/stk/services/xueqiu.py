"""Xueqiu watchlist API adapter."""

from collections.abc import Iterable
from typing import Any, Final

import requests

from stk.config import settings
from stk.errors import ConfigError, SourceError
from stk.models.watchlist import Watchlist, WatchlistSecurity, WatchlistSummary

DEFAULT_WATCHLIST_ID: Final = "-1"
DEFAULT_WATCHLIST_NAME: Final = "我的自选"
_BASE_URL: Final = "https://stock.xueqiu.com/v5/stock/portfolio"
_LIST_GROUPS_URL: Final = f"{_BASE_URL}/list.json"
_LIST_STOCKS_URL: Final = f"{_BASE_URL}/stock/list.json"
_ADD_STOCK_URL: Final = f"{_BASE_URL}/stock/add.json"
_CANCEL_STOCK_URL: Final = f"{_BASE_URL}/stock/cancel.json"
_MODIFY_PORTFOLIO_URL: Final = f"{_BASE_URL}/stock/modify_portfolio.json"
_CREATE_GROUP_URL: Final = f"{_BASE_URL}/create.json"
_DELETE_GROUP_URL: Final = f"{_BASE_URL}/delete.json"


class XueqiuClient:
    """Authenticated client for Xueqiu stock watchlists."""

    def __init__(self, session: requests.Session | None = None) -> None:
        missing = [
            name
            for name, value in (
                ("XUEQIU_UID", settings.xueqiu_uid),
                ("XUEQIU_A_TOKEN", settings.xueqiu_a_token),
                ("XUEQIU_ID_TOKEN", settings.xueqiu_id_token),
            )
            if not value
        ]
        if missing:
            raise ConfigError(f"Missing Xueqiu configuration: {', '.join(missing)}")

        self._session = session or requests.Session()
        self._session.cookies.update({
            "u": settings.xueqiu_uid,
            "xq_a_token": settings.xueqiu_a_token,
            "xq_id_token": settings.xueqiu_id_token,
        })
        self._session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://xueqiu.com",
            "Referer": "https://xueqiu.com/",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138 Safari/537.36"
            ),
        })

    def _request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = self._session.request(method, url, timeout=10, **kwargs)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as err:
            raise SourceError(f"Xueqiu request failed: {err}") from err
        if not isinstance(payload, dict):
            raise SourceError("Xueqiu returned an invalid response")
        error_code = payload.get("error_code", 0)
        if error_code not in (0, None) or payload.get("success") is False:
            message = payload.get("error_description") or payload.get("error") or "unknown error"
            raise SourceError(f"Xueqiu API error {error_code}: {message}")
        return payload

    def _raw_groups(self) -> list[dict[str, Any]]:
        payload = self._request("GET", _LIST_GROUPS_URL, params={"system": "true"})
        data = payload.get("data")
        if not isinstance(data, dict) or not isinstance(data.get("stocks"), list):
            raise SourceError("Xueqiu group response is missing stocks")
        return [item for item in data["stocks"] if isinstance(item, dict)]

    def list_groups(self) -> list[WatchlistSummary]:
        groups: list[WatchlistSummary] = []
        for item in self._raw_groups():
            group_id = str(item.get("id", ""))
            name = DEFAULT_WATCHLIST_NAME if group_id == DEFAULT_WATCHLIST_ID else str(item["name"])
            groups.append(
                WatchlistSummary(
                    id=group_id,
                    name=name,
                    count=int(item.get("symbol_count", 0)),
                    readonly=int(item.get("type", -1)) == -1 and group_id != DEFAULT_WATCHLIST_ID,
                )
            )
        return groups

    def resolve_group(self, name: str) -> WatchlistSummary:
        matches = [group for group in self.list_groups() if group.name == name]
        if not matches:
            raise SourceError(f"Xueqiu group not found: {name}")
        if len(matches) > 1:
            raise SourceError(f"Xueqiu group name is ambiguous: {name}")
        return matches[0]

    def get_watchlist(self, name: str = DEFAULT_WATCHLIST_NAME) -> Watchlist:
        group = self.resolve_group(name)
        payload = self._request(
            "GET",
            _LIST_STOCKS_URL,
            params={"size": 1000, "category": 1, "pid": group.id},
        )
        data = payload.get("data")
        if not isinstance(data, dict) or not isinstance(data.get("stocks"), list):
            raise SourceError("Xueqiu watchlist response is missing stocks")
        securities = [
            WatchlistSecurity(
                symbol=str(item.get("symbol", "")),
                market=str(item.get("exchange", "")),
                name=str(item.get("name", "")),
            )
            for item in data["stocks"]
            if isinstance(item, dict) and item.get("symbol")
        ]
        return Watchlist(
            id=group.id,
            name=group.name,
            count=len(securities),
            securities=securities,
        )

    def create_group(self, name: str) -> Watchlist:
        if any(group.name == name for group in self.list_groups()):
            raise SourceError(f"Xueqiu group already exists: {name}")
        self._request("POST", _CREATE_GROUP_URL, data={"category": 1, "pnames": name})
        return self.get_watchlist(name)

    def delete_group(self, name: str) -> None:
        group = self.resolve_group(name)
        self._ensure_writable_custom_group(group)
        self._request("POST", _DELETE_GROUP_URL, data={"pids": group.id})

    @staticmethod
    def _ensure_writable_custom_group(group: WatchlistSummary) -> None:
        if group.readonly or group.id == DEFAULT_WATCHLIST_ID:
            raise SourceError(f"Xueqiu group cannot be modified as a custom group: {group.name}")

    def _custom_memberships(self, symbols: set[str]) -> dict[str, set[str]]:
        memberships = {symbol: set() for symbol in symbols}
        custom_groups = [
            group
            for group in self.list_groups()
            if not group.readonly and group.id != DEFAULT_WATCHLIST_ID
        ]
        for group in custom_groups:
            for item in self.get_watchlist(group.name).securities:
                if item.symbol in memberships:
                    memberships[item.symbol].add(group.name)
        return memberships

    def add_stocks(self, name: str, symbols: Iterable[str]) -> int:
        requested = set(symbols)
        if not requested:
            return 0
        group = self.resolve_group(name)
        if group.id == DEFAULT_WATCHLIST_ID:
            self._request("POST", _ADD_STOCK_URL, data={"symbols": ",".join(sorted(requested))})
            return len(requested)
        self._ensure_writable_custom_group(group)
        memberships = self._custom_memberships(requested)
        for symbol in sorted(requested):
            names = memberships[symbol] | {group.name}
            self._modify_memberships(symbol, names)
        return len(requested)

    def remove_stocks(self, name: str, symbols: Iterable[str]) -> int:
        requested = set(symbols)
        if not requested:
            return 0
        group = self.resolve_group(name)
        if group.id == DEFAULT_WATCHLIST_ID:
            self._request("POST", _CANCEL_STOCK_URL, data={"symbols": ",".join(sorted(requested))})
            return len(requested)
        self._ensure_writable_custom_group(group)
        memberships = self._custom_memberships(requested)
        for symbol in sorted(requested):
            self._modify_memberships(symbol, memberships[symbol] - {group.name})
        return len(requested)

    def _modify_memberships(self, symbol: str, names: set[str]) -> None:
        self._request(
            "POST",
            _MODIFY_PORTFOLIO_URL,
            data={"symbols": symbol, "pnames": ",".join(sorted(names)), "category": 1},
        )


def list_xueqiu_groups() -> list[WatchlistSummary]:
    return XueqiuClient().list_groups()


def get_xueqiu_watchlist(name: str = DEFAULT_WATCHLIST_NAME) -> Watchlist:
    return XueqiuClient().get_watchlist(name)


def create_xueqiu_group(name: str) -> Watchlist:
    return XueqiuClient().create_group(name)


def delete_xueqiu_group(name: str) -> None:
    XueqiuClient().delete_group(name)


def add_xueqiu_stocks(name: str, symbols: Iterable[str]) -> int:
    return XueqiuClient().add_stocks(name, symbols)


def remove_xueqiu_stocks(name: str, symbols: Iterable[str]) -> int:
    return XueqiuClient().remove_stocks(name, symbols)
