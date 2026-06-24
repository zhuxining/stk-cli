"""Cross-platform watchlist sync orchestration."""

from collections.abc import Sequence
from typing import Any

from loguru import logger

from stk.models.sync import SyncDiff, SyncItem, SyncResult
from stk.utils.symbol import from_ths_symbol, is_longport_symbol, to_ths_symbol


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
        diff.to_add = [SyncItem(symbol=t, action="add", ths_symbol=t) for t in sorted(all_lp)]
        diff.unchanged = 0

    added = 0
    removed = 0

    # Add before remove: if add fails (e.g. invalid symbol), we don't lose data
    # that was already correctly in the target group.
    if diff.to_add:
        try:
            symbols = [item.ths_symbol for item in diff.to_add]
            added = add_ths_stocks(to_group, symbols)
        except Exception as e:
            errors.append(f"添加失败: {e}")

    if diff.to_remove:
        try:
            symbols = [item.ths_symbol for item in diff.to_remove]
            removed = remove_ths_stocks(to_group, symbols)
        except Exception as e:
            errors.append(f"删除失败: {e}")

    return SyncResult(
        action="push",
        diff=diff,
        added=added,
        removed=removed,
        errors=errors,
    )


def _ths_group_to_lp_symbols(group_data: dict[str, Any]) -> list[str]:
    """Convert THS group items to Longport symbols.

    Drops assets that longport cannot hold (indices, funds, bonds, futures),
    because update_watchlist_group is batch-based and one invalid symbol can
    fail the whole batch.
    """
    result: list[str] = []
    for item in group_data["items"]:
        market = (item.market or "").upper()
        if not item.code or not market:
            continue
        ths_sym = f"{item.code}.{market}"
        lp = from_ths_symbol(ths_sym)
        if not is_longport_symbol(lp):
            logger.debug(f"跳过 longport 不支持的 THS 标的: {ths_sym} -> {lp}")
            continue
        result.append(lp)
    return result


def pull_from_ths(from_group: str, to_group: str, *, replace: bool = False) -> SyncResult:
    """Pull a THS watchlist group into a Longport group.

    Args:
        from_group: THS group name (source).
        to_group: Longport group name (target). Created if not exists.
        replace: If True, clear target group first then add all.
    """
    from longport.openapi import SecuritiesUpdateMode

    from stk.errors import SourceError
    from stk.services.ths_wrapper import get_ths_group
    from stk.services.watchlist import add_symbols, create_group, get_watchlist, remove_symbols

    errors: list[str] = []

    # Get THS group stocks
    ths_group = get_ths_group(from_group)
    if ths_group["readonly"]:
        logger.warning(f"同花顺分组 '{from_group}' 是动态板块，不支持拉取")
    ths_lp_symbols = _ths_group_to_lp_symbols(ths_group)
    ths_set = set(ths_lp_symbols)

    # Ensure target Longport group exists
    try:
        get_watchlist(to_group)
    except Exception:
        logger.info(f"长桥分组 '{to_group}' 不存在，自动创建")
        try:
            create_group(to_group)
        except Exception as e:
            raise SourceError(f"创建长桥分组 '{to_group}' 失败: {e}") from e

    # --replace: use a single Replace-mode API call (clear + set in one shot).
    # This avoids the intersection bug where stocks present in both groups
    # get added then immediately removed by the two-step diff approach.
    if replace:
        try:
            add_symbols(to_group, sorted(ths_set), mode=SecuritiesUpdateMode.Replace)
        except Exception as e:
            errors.append(f"替代失败: {e}")
        return SyncResult(
            action="pull",
            diff=SyncDiff(
                from_group=from_group,
                to_group=to_group,
                to_add=[SyncItem(symbol=s, action="add") for s in sorted(ths_set)],
                to_remove=[],
                unchanged=0,
            ),
            added=len(ths_set),
            removed=0,
            errors=errors,
        )

    # Get Longport group securities
    try:
        watchlist = get_watchlist(to_group)
    except Exception as e:
        raise SourceError(f"获取长桥分组 '{to_group}' 失败: {e}") from e
    lp_set = {s.symbol for s in watchlist.securities}

    to_add = ths_set - lp_set
    to_remove = lp_set - ths_set
    unchanged = len(ths_set & lp_set)

    diff = SyncDiff(
        from_group=from_group,
        to_group=to_group,
        to_add=[SyncItem(symbol=s, action="add") for s in sorted(to_add)],
        to_remove=[SyncItem(symbol=s, action="remove") for s in sorted(to_remove)],
        unchanged=unchanged,
    )

    added = 0
    removed = 0

    # Add before remove: if add fails (e.g. invalid symbol), we don't lose data
    # that was already correctly in the target group.
    if diff.to_add:
        try:
            symbols = [item.symbol for item in diff.to_add]
            add_symbols(to_group, symbols)
            added = len(symbols)
        except Exception as e:
            errors.append(f"添加失败: {e}")

    if diff.to_remove:
        try:
            symbols = [item.symbol for item in diff.to_remove]
            remove_symbols(to_group, symbols)
            removed = len(symbols)
        except Exception as e:
            errors.append(f"删除失败: {e}")

    return SyncResult(
        action="pull",
        diff=diff,
        added=added,
        removed=removed,
        errors=errors,
    )
