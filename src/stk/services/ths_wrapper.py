"""Thin wrapper around ths-favorite PortfolioManager for stk-cli."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from stk.config import settings
from stk.errors import ConfigError, SourceError

# Patch: override the library's default CACHE_FILE to live under ~/.stk/
import config as _ths_config  # type: ignore[import-untyped]

_ths_config.CACHE_FILE = str(settings.data_dir / "ths_favorite_cache.json")

if TYPE_CHECKING:
    from stk.models.sync import ThsGroup


def _resolve_ths_auth() -> dict[str, str]:
    """Resolve THS auth kwargs for PortfolioManager."""
    if settings.ths_username and settings.ths_password:
        logger.info("使用账号密码登录同花顺")
        return {
            "username": settings.ths_username,
            "password": settings.ths_password,
        }
    raise ConfigError(
        "同花顺认证未配置。请在 .env 中设置：\n"
        "  THS_USERNAME=手机号\n"
        "  THS_PASSWORD=密码"
    )


@contextmanager
def get_ths_portfolio() -> Generator[None]:
    """Yield a PortfolioManager instance.

    Uses username+password auth. Cookie cache stored under ~/.stk/.

    Raises ConfigError if auth is not configured.
    Raises SourceError on THS API failures.
    """
    from exceptions import THSError  # type: ignore[import-untyped]
    from service import PortfolioManager  # type: ignore[import-untyped]

    auth_kwargs = _resolve_ths_auth()

    try:
        with PortfolioManager(
            **auth_kwargs,
            cookie_cache_path=str(settings.data_dir / "ths_cookie_cache.json"),
        ) as pm:
            yield pm
    except THSError as e:
        raise SourceError(f"同花顺 API 错误: {e}") from e


def list_ths_groups() -> list[ThsGroup]:
    """List all THS watchlist groups.

    Returns list[ThsGroup] (imported lazily to avoid circular imports).
    """
    from stk.models.sync import ThsGroup

    with get_ths_portfolio() as pm:
        groups = pm.get_all_groups(include_self_stocks=True)
        result = []
        for name, g in groups.items():
            result.append(
                ThsGroup(
                    name=name,
                    group_id=g.group_id,
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
    """

    with get_ths_portfolio() as pm:
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
