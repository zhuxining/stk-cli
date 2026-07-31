"""Longport and THS group commands."""

import typer

from stk import output
from stk.errors import StkError
from stk.models.common import MutationResult
from stk.models.watchlist import GroupDetailResult, GroupListResult, WatchlistSummary

app = typer.Typer(help="Manage and synchronize security groups", no_args_is_help=True)
longport_app = typer.Typer(help="Manage Longport groups", no_args_is_help=True)
ths_app = typer.Typer(help="Inspect THS groups", no_args_is_help=True)
sync_app = typer.Typer(help="Synchronize Longport and THS groups", no_args_is_help=True)

app.add_typer(longport_app, name="longport")
app.add_typer(ths_app, name="ths")
app.add_typer(sync_app, name="sync")


@longport_app.command("list")
def longport_list() -> None:
    from stk.services.watchlist import list_watchlists

    output.render(GroupListResult(platform="longport", groups=list_watchlists()))


@longport_app.command()
def show(name: str = typer.Argument(help="Longport group name")) -> None:
    from stk.services.watchlist import get_watchlist

    output.render(GroupDetailResult(platform="longport", group=get_watchlist(name)))


@longport_app.command()
def create(
    name: str = typer.Argument(help="New Longport group name"),
    symbols: list[str] | None = typer.Option(None, "--symbol", "-s", help="Initial symbols"),
) -> None:
    from stk.services.watchlist import create_group
    from stk.utils.symbol import expand_symbols

    expanded = expand_symbols(symbols or [])
    output.render(
        GroupDetailResult(
            platform="longport",
            group=create_group(name, symbols=expanded or None),
        )
    )


@longport_app.command()
def add(
    name: str = typer.Argument(help="Longport group name"),
    symbols: list[str] = typer.Argument(help="Symbols to add"),
) -> None:
    from stk.services.watchlist import add_symbols
    from stk.utils.symbol import expand_symbols, to_longport_symbol

    expanded = [to_longport_symbol(item) for item in expand_symbols(symbols)]
    add_symbols(name, expanded)
    output.render(
        MutationResult(
            operation="add",
            platform="longport",
            group=name,
            requested_symbols=expanded,
        )
    )


@longport_app.command()
def remove(
    name: str = typer.Argument(help="Longport group name"),
    symbols: list[str] = typer.Argument(help="Symbols to remove"),
) -> None:
    from stk.services.watchlist import remove_symbols
    from stk.utils.symbol import expand_symbols, to_longport_symbol

    expanded = [to_longport_symbol(item) for item in expand_symbols(symbols)]
    remove_symbols(name, expanded)
    output.render(
        MutationResult(
            operation="remove",
            platform="longport",
            group=name,
            requested_symbols=expanded,
        )
    )


@longport_app.command()
def delete(name: str = typer.Argument(help="Longport group name")) -> None:
    from stk.services.watchlist import delete_group

    delete_group(name)
    output.render(MutationResult(operation="delete", platform="longport", group=name))


@ths_app.command("list")
def ths_list() -> None:
    from stk.services.ths_wrapper import list_ths_groups

    groups = [
        WatchlistSummary(
            id=item.id,
            name=item.name,
            count=item.count,
            readonly=item.readonly,
        )
        for item in list_ths_groups()
    ]
    output.render(GroupListResult(platform="ths", groups=groups))


@sync_app.command()
def diff(
    from_group: str = typer.Argument(help="Longport source group"),
    to_group: str | None = typer.Argument(None, help="THS target group"),
) -> None:
    from stk.services.sync import compute_diff

    output.render(compute_diff(from_group, to_group or from_group))


@sync_app.command()
def push(
    from_group: str = typer.Argument(help="Longport source group"),
    to_group: str | None = typer.Argument(None, help="THS target group"),
    replace: bool = typer.Option(False, "--replace", "-r", help="Replace target contents"),
) -> None:
    from stk.services.sync import push_to_ths

    output.render(push_to_ths(from_group, to_group or from_group, replace=replace))


@sync_app.command()
def pull(
    from_group: str = typer.Argument(help="THS source group"),
    to_group: str | None = typer.Argument(None, help="Longport target group"),
    replace: bool = typer.Option(False, "--replace", "-r", help="Replace target contents"),
) -> None:
    from stk.services.sync import pull_from_ths

    output.render(pull_from_ths(from_group, to_group or from_group, replace=replace))


@app.command()
def route(
    src: str = typer.Argument(help="Longport source group"),
    buy_dst: str = typer.Argument(help="Current buy-signal snapshot group"),
    sell_dst: str = typer.Argument(help="Current sell-signal snapshot group"),
    replace: bool = typer.Option(
        True,
        "--replace/--append",
        help="Refresh destination snapshots (default) or append only",
    ),
) -> None:
    if len({src, buy_dst, sell_dst}) != 3:
        raise StkError("Source, buy-signal, and sell-signal groups must be different")

    from stk.services.watchlist import route_signals

    output.render(route_signals(src, buy_dst, sell_dst, replace=replace))
