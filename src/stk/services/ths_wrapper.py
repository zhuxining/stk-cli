"""Thin wrapper around ths-favorite PortfolioManager for stk-cli."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
import time
from typing import TYPE_CHECKING

# Patch: override the library's default CACHE_FILE to live under ~/.stk/
import config as _ths_config  # type: ignore[import-untyped]
from loguru import logger

from stk.config import settings
from stk.errors import ConfigError, SourceError

_ths_config.CACHE_FILE = str(settings.data_dir / "ths_favorite_cache.json")

if TYPE_CHECKING:
    from stk.models.sync import ThsGroup


def _harden_dynamic_plate() -> None:
    """Harden upstream dynamic-plate queries against empty/204 responses.

    ths-favorite's ``dynamicplate.query_dynamic_plate`` calls ``response.json()``
    outside its try/except, so an intermittent ``204 No Content`` from
    apigate.10jqka.com.cn raises ``requests.JSONDecodeError`` which escapes
    ``PortfolioManager.get_all_groups`` and aborts the whole group fetch
    ("Expecting value: line 1 column 1").

    We patch ``FavoriteAPI.query_dynamic_plate`` to retry briefly and finally
    raise ``THSNetworkError`` — upstream ``get_all_groups`` already handles that
    by degrading the dynamic group to an empty list, keeping normal groups
    (e.g. 资产ETF) intact.
    """
    try:
        from api import FavoriteAPI  # type: ignore[import-untyped]
        from exceptions import THSNetworkError  # type: ignore[import-untyped]
        from requests.exceptions import RequestException
    except ImportError:
        return

    original = FavoriteAPI.query_dynamic_plate

    def _query_with_retry(self, group_name: str) -> list:  # type: ignore[type-arg]
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                return original(self, group_name)
            except RequestException as err:
                last_error = err
                logger.warning(
                    "动态板块「{}」接口响应异常（第 {} 次）：{}",
                    group_name,
                    attempt + 1,
                    err,
                )
                if attempt < 2:
                    time.sleep(0.5 * (attempt + 1))
        assert last_error is not None
        raise THSNetworkError(f"查询动态板块「{group_name}」", str(last_error)) from last_error

    FavoriteAPI.query_dynamic_plate = _query_with_retry


_harden_dynamic_plate()


def _check_ths_auth() -> None:
    """Check THS auth is configured."""
    if not settings.ths_username or not settings.ths_password:
        raise ConfigError(
            "同花顺认证未配置。请在 .env 中设置：\n  THS_USERNAME=手机号\n  THS_PASSWORD=密码"
        )


@contextmanager
def get_ths_portfolio() -> Generator:  # type: ignore[type-arg]
    """Yield a PortfolioManager instance.

    Uses username+password auth. Cookie cache stored under ~/.stk/.

    Raises ConfigError if auth is not configured.
    Raises SourceError on THS API failures.
    """
    from exceptions import THSError  # type: ignore[import-untyped]
    from requests.exceptions import RequestException
    from service import PortfolioManager  # type: ignore[import-untyped]

    _check_ths_auth()

    try:
        with PortfolioManager(
            username=settings.ths_username,
            password=settings.ths_password,
            cookie_cache_path=str(settings.data_dir / "ths_cookie_cache.json"),
        ) as pm:
            try:
                yield pm
            except THSError as e:
                raise SourceError(f"同花顺 API 错误: {e}") from e
            except RequestException as e:
                raise SourceError(
                    f"同花顺接口响应异常（可能为动态板块偶发空响应），请稍后重试：{e}"
                ) from e
    except THSError as e:
        raise SourceError(f"同花顺 API 错误: {e}") from e


def list_ths_groups() -> list[ThsGroup]:
    """List all THS watchlist groups.

    Returns list[ThsGroup] (imported lazily to avoid circular imports).
    """
    from stk.models.sync import ThsGroup

    with get_ths_portfolio() as pm:
        groups = pm.get_all_groups(include_self_stocks=True)
        # Self-stock from get_all_groups may be stale (uses refresh=False);
        # force-refresh so count is accurate.
        if _ths_config.SELF_STOCK_DEFAULT_NAME in groups:
            fresh = pm.get_self_stocks(refresh=True)
            groups[fresh.name] = fresh
        result = []
        for name, g in groups.items():
            result.append(
                ThsGroup(
                    id=str(g.group_id),
                    name=name,
                    count=len(g.items),
                    readonly=g.readonly,
                )
            )
        logger.info(f"获取到 {len(result)} 个同花顺分组")
        return result


def get_ths_group(name: str) -> dict[str, object]:
    """Get a single THS group with its stock items.

    Returns dict with keys: 'name', 'group_id', 'items', 'readonly'.
    Each item is a StockItem (code, market) from ths-favorite.

    Note: when name is the self-stock group ("我的自选"), get_all_groups
    internally calls get_self_stocks(refresh=False) which uses a stale
    in-memory cache. We force-refresh it here to get the real list.
    """

    with get_ths_portfolio() as pm:
        # Self-stock ("我的自选") needs explicit refresh=True — see above.
        if name == _ths_config.SELF_STOCK_DEFAULT_NAME:
            g = pm.get_self_stocks(refresh=True)
        else:
            groups = pm.get_all_groups(include_self_stocks=True)
            if name not in groups:
                raise SourceError(f"同花顺分组 '{name}' 不存在")
            g = groups[name]
        return {
            "name": g.name,
            "group_id": g.group_id,
            "items": list(g.items),
            "readonly": g.readonly,
        }


def create_ths_group(name: str) -> dict[str, object]:
    """Create a new THS watchlist group.

    Works around upstream bug: PortfolioManager.add_group() calls
    _api.add_group() but FavoriteAPI method is named create_group().
    """

    with get_ths_portfolio() as pm:
        pm.get_all_groups(use_cache=False)
        version = str(pm._current_version or "")
        result = pm._api.create_group(name, version)
        pm.get_all_groups(use_cache=False)
        logger.info(f"已创建同花顺分组: {name}")
        return result


def add_ths_stocks(name: str, symbols: list[str]) -> int:
    """Add stocks to a THS group (batch). Returns count added.

    Args:
        name: THS group name.
        symbols: List of THS-format symbols (e.g., ['600519.SH', '000858.SZ']).
    """
    if not symbols:
        return 0
    with get_ths_portfolio() as pm:
        pm.add_items(name, symbols)
        logger.info(f"已添加 {len(symbols)} 只股票到同花顺分组 '{name}'")
        return len(symbols)


def remove_ths_stocks(name: str, symbols: list[str]) -> int:
    """Remove stocks from a THS group (batch). Returns count removed.

    Args:
        name: THS group name.
        symbols: List of THS-format symbols.
    """
    if not symbols:
        return 0
    with get_ths_portfolio() as pm:
        pm.remove_items(name, symbols)
        logger.info(f"已从同花顺分组 '{name}' 删除 {len(symbols)} 只股票")
        return len(symbols)
