"""Cross-platform watchlist sync orchestration."""

from collections.abc import Sequence
from typing import Any

from loguru import logger

from stk.models.sync import SyncDiff, SyncItem, SyncResult
from stk.utils.symbol import to_ths_symbol


def _build_ths_set(group_data: dict[str, Any]) -> set[str]:
    """Build a set of normalized THS symbols from group data.

    THS StockItem uses (code, market) format. We normalize to 'CODE.MARKET'
    for consistent comparison.
    """
    result: set[str] = set()
    for item in group_data["items"]:
        code = item.code
        market = (item.market or "").upper()
        if code and market:
            result.add(f"{code}.{market}")
    return result


def _normalize_longport_symbols(symbols: Sequence[str]) -> set[str]:
    """Convert longport symbols to THS-comparable format."""
    result: set[str] = set()
    for s in symbols:
        t = to_ths_symbol(s)
        if "." not in t:
            logger.debug(f"跳过无法转换的股票: {s}")
            continue
        code = t.split(".")[0]
        if not code.isdigit():
            logger.debug(f"跳过非数字代码: {s}")
            continue
        result.add(t)
    return result


def compute_diff(from_group: str, to_group: str) -> SyncDiff:
    """Compute the difference between a longport group and a THS group.

    Args:
        from_group: Longport watchlist group name.
        to_group: THS group name.

    Returns:
        SyncDiff with to_add and to_remove lists.
    """
    from stk.services.ths_wrapper import get_ths_group
    from stk.services.watchlist import get_watchlist

    # Get longport group securities
    watchlist = get_watchlist(from_group)
    lp_symbols = [s.symbol for s in watchlist.securities]
    lp_set = _normalize_longport_symbols(lp_symbols)

    # Get THS group securities (may raise if group doesn't exist)
    ths_group = get_ths_group(to_group)
    if ths_group["readonly"]:
        logger.warning(f"同花顺分组 '{to_group}' 是动态板块（只读），不能写入")

    ths_set = _build_ths_set(ths_group)

    # Compute differences
    to_add_symbols = lp_set - ths_set
    to_remove_symbols = ths_set - lp_set
    unchanged = len(lp_set & ths_set)

    to_add = [
        SyncItem(
            symbol=t,
            action="add",
            ths_symbol=t,
        )
        for t in sorted(to_add_symbols)
    ]
    to_remove = [
        SyncItem(
            symbol=t,
            action="remove",
            ths_symbol=t,
        )
        for t in sorted(to_remove_symbols)
    ]

    return SyncDiff(
        from_group=from_group,
        to_group=to_group,
        to_add=to_add,
        to_remove=to_remove,
        unchanged=unchanged,
    )


def push_to_ths(from_group: str, to_group: str, *, replace: bool = False) -> SyncResult:
    """Push a longport watchlist group to a THS group.

    Args:
        from_group: Longport group name.
        to_group: THS group name. Created if not exists.
        replace: If True, clear target group first then add all.
    """
    from stk.errors import SourceError
    from stk.services.ths_wrapper import (
        add_ths_stocks,
        create_ths_group,
        get_ths_group,
        remove_ths_stocks,
    )

    errors: list[str] = []

    # Ensure target group exists
    try:
        get_ths_group(to_group)
    except SourceError:
        logger.info(f"同花顺分组 '{to_group}' 不存在，自动创建")
        try:
            create_ths_group(to_group)
        except Exception as e:
            raise SourceError(f"创建同花顺分组 '{to_group}' 失败: {e}") from e

    diff = compute_diff(from_group, to_group)

    if replace:
        # In replace mode: remove all existing, add all from source
        # Override the diff
        all_ths = _build_ths_set(get_ths_group(to_group))
        from stk.services.watchlist import get_watchlist

        watchlist = get_watchlist(from_group)
        all_lp = _normalize_longport_symbols([s.symbol for s in watchlist.securities])

        diff.to_remove = [
            SyncItem(symbol=t, action="remove", ths_symbol=t) for t in sorted(all_ths)
        ]
        diff.to_add = [
            SyncItem(symbol=t, action="add", ths_symbol=t) for t in sorted(all_lp)
        ]
        diff.unchanged = 0

    added = 0
    removed = 0

    if diff.to_remove:
        try:
            symbols = [item.ths_symbol for item in diff.to_remove]
            removed = remove_ths_stocks(to_group, symbols)
        except Exception as e:
            errors.append(f"删除失败: {e}")

    if diff.to_add:
        try:
            symbols = [item.ths_symbol for item in diff.to_add]
            added = add_ths_stocks(to_group, symbols)
        except Exception as e:
            errors.append(f"添加失败: {e}")

    return SyncResult(
        action="push",
        diff=diff,
        added=added,
        removed=removed,
        errors=errors,
    )
