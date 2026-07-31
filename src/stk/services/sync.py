"""Cross-platform group synchronization orchestration."""

from collections.abc import Iterable
from typing import Any

from loguru import logger

from stk.errors import SourceError
from stk.models.sync import (
    AppliedChanges,
    SyncChanges,
    SyncEndpoint,
    SyncFailure,
    SyncResult,
)
from stk.utils.symbol import from_ths_symbol, is_longport_symbol, to_ths_symbol


def _build_ths_set(group_data: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for item in group_data["items"]:
        code = item.code
        market = (item.market or "").upper()
        if code and market:
            result.add(f"{code}.{market}")
    return result


def _normalize_longport_symbols(symbols: Iterable[str]) -> set[str]:
    result: set[str] = set()
    for symbol in symbols:
        converted = to_ths_symbol(symbol)
        code = converted.split(".")[0]
        if "." not in converted or not code.isdigit():
            logger.debug(f"跳过无法同步到同花顺的标的: {symbol}")
            continue
        result.add(converted)
    return result


def _endpoints(
    operation: str,
    from_group: str,
    to_group: str,
) -> tuple[SyncEndpoint, SyncEndpoint]:
    if operation == "pull":
        return (
            SyncEndpoint(platform="ths", group=from_group),
            SyncEndpoint(platform="longport", group=to_group),
        )
    return (
        SyncEndpoint(platform="longport", group=from_group),
        SyncEndpoint(platform="ths", group=to_group),
    )


def compute_diff(from_group: str, to_group: str) -> SyncResult:
    from stk.services.ths_wrapper import get_ths_group
    from stk.services.watchlist import get_watchlist

    longport = get_watchlist(from_group)
    source = _normalize_longport_symbols(item.symbol for item in longport.securities)
    ths_group = get_ths_group(to_group)
    target = _build_ths_set(ths_group)
    warnings = [f"同花顺分组“{to_group}”为只读动态板块"] if ths_group["readonly"] else []
    source_endpoint, target_endpoint = _endpoints("diff", from_group, to_group)
    return SyncResult(
        operation="diff",
        mode="preview",
        source=source_endpoint,
        target=target_endpoint,
        changes=SyncChanges(
            add_symbols=sorted(source - target),
            remove_symbols=sorted(target - source),
            unchanged_count=len(source & target),
        ),
        warnings=warnings,
    )


def push_to_ths(from_group: str, to_group: str, *, replace: bool = False) -> SyncResult:
    from stk.services.ths_wrapper import (
        add_ths_stocks,
        create_ths_group,
        get_ths_group,
        remove_ths_stocks,
    )
    from stk.services.watchlist import get_watchlist

    longport = get_watchlist(from_group)
    source = _normalize_longport_symbols(item.symbol for item in longport.securities)
    warnings: list[str] = []
    try:
        ths_group = get_ths_group(to_group)
        target = _build_ths_set(ths_group)
        if ths_group["readonly"]:
            warnings.append(f"同花顺分组“{to_group}”为只读动态板块")
    except SourceError:
        create_ths_group(to_group)
        target = set()

    add_symbols = sorted(source - target)
    remove_symbols = sorted(target - source) if replace else []
    failures: list[SyncFailure] = []
    added_count = 0
    removed_count = 0
    if add_symbols:
        try:
            added_count = add_ths_stocks(to_group, add_symbols)
        except Exception as err:
            failures.append(SyncFailure(operation="add", message=str(err)))
    if remove_symbols:
        try:
            removed_count = remove_ths_stocks(to_group, remove_symbols)
        except Exception as err:
            failures.append(SyncFailure(operation="remove", message=str(err)))

    source_endpoint, target_endpoint = _endpoints("push", from_group, to_group)
    return SyncResult(
        operation="push",
        mode="replace" if replace else "merge",
        source=source_endpoint,
        target=target_endpoint,
        changes=SyncChanges(
            add_symbols=add_symbols,
            remove_symbols=remove_symbols,
            unchanged_count=len(source & target),
        ),
        applied=AppliedChanges(
            added_count=added_count,
            removed_count=removed_count,
        ),
        failures=failures,
        warnings=warnings,
    )


def _ths_group_to_lp_symbols(group_data: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for item in group_data["items"]:
        market = (item.market or "").upper()
        if not item.code or not market:
            continue
        ths_symbol = f"{item.code}.{market}"
        longport_symbol = from_ths_symbol(ths_symbol)
        if is_longport_symbol(longport_symbol):
            result.add(longport_symbol)
        else:
            logger.debug(f"跳过 Longport 不支持的标的: {ths_symbol}")
    return result


def pull_from_ths(from_group: str, to_group: str, *, replace: bool = False) -> SyncResult:
    from longport.openapi import SecuritiesUpdateMode

    from stk.services.ths_wrapper import get_ths_group
    from stk.services.watchlist import add_symbols, get_watchlist

    ths_group = get_ths_group(from_group)
    source = _ths_group_to_lp_symbols(ths_group)
    warnings = [f"同花顺分组“{from_group}”为只读动态板块"] if ths_group["readonly"] else []
    try:
        target_group = get_watchlist(to_group)
        target = {item.symbol for item in target_group.securities}
    except SourceError:
        target = set()

    add_plan = sorted(source - target)
    remove_plan = sorted(target - source) if replace else []
    failures: list[SyncFailure] = []
    added_count = 0
    removed_count = 0
    try:
        if replace:
            add_symbols(to_group, sorted(source), mode=SecuritiesUpdateMode.Replace)
            added_count = len(source)
            removed_count = len(remove_plan)
        elif add_plan:
            add_symbols(to_group, add_plan, mode=SecuritiesUpdateMode.Add)
            added_count = len(add_plan)
    except Exception as err:
        failures.append(
            SyncFailure(
                operation="replace" if replace else "add",
                message=str(err),
            )
        )
        added_count = 0
        removed_count = 0

    source_endpoint, target_endpoint = _endpoints("pull", from_group, to_group)
    return SyncResult(
        operation="pull",
        mode="replace" if replace else "merge",
        source=source_endpoint,
        target=target_endpoint,
        changes=SyncChanges(
            add_symbols=add_plan,
            remove_symbols=remove_plan,
            unchanged_count=len(source & target),
        ),
        applied=AppliedChanges(
            added_count=added_count,
            removed_count=removed_count,
        ),
        failures=failures,
        warnings=warnings,
    )
