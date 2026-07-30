"""Longport and THS group commands."""

import typer

from stk import output
from stk.errors import StkError
from stk.models.common import ActionResult
from stk.models.sync import SyncResult

app = typer.Typer(help="Manage and synchronize security groups", no_args_is_help=True)
longport_app = typer.Typer(help="Manage Longport groups", no_args_is_help=True)
ths_app = typer.Typer(help="Inspect THS groups", no_args_is_help=True)
sync_app = typer.Typer(help="Synchronize Longport and THS groups", no_args_is_help=True)

app.add_typer(longport_app, name="longport")
app.add_typer(ths_app, name="ths")
app.add_typer(sync_app, name="sync")


@longport_app.command("list")
def longport_list() -> None:
    """List Longport groups."""
    from stk.services.watchlist import list_watchlists

    output.render(list_watchlists(), meta={"platform": "longport"})


@longport_app.command()
def show(name: str = typer.Argument(help="Longport group name")) -> None:
    """Show securities in a Longport group."""
    from stk.services.watchlist import get_watchlist

    output.render(get_watchlist(name), meta={"platform": "longport"})


@longport_app.command()
def create(
    name: str = typer.Argument(help="New Longport group name"),
    symbols: list[str] | None = typer.Option(None, "--symbol", "-s", help="Initial symbols"),
) -> None:
    """Create a Longport group."""
    from stk.services.watchlist import create_group
    from stk.utils.symbol import expand_symbols

    expanded = expand_symbols(symbols or [])
    output.render(create_group(name, symbols=expanded or None))


@longport_app.command()
def add(
    name: str = typer.Argument(help="Longport group name"),
    symbols: list[str] = typer.Argument(help="Symbols to add"),
) -> None:
    """Add symbols to a Longport group."""
    from stk.services.watchlist import add_symbols
    from stk.utils.symbol import expand_symbols

    expanded = expand_symbols(symbols)
    add_symbols(name, expanded)
    output.render(ActionResult(message=f"Added {len(expanded)} symbols to {name}"))


@longport_app.command()
def remove(
    name: str = typer.Argument(help="Longport group name"),
    symbols: list[str] = typer.Argument(help="Symbols to remove"),
) -> None:
    """Remove symbols from a Longport group."""
    from stk.services.watchlist import remove_symbols
    from stk.utils.symbol import expand_symbols

    expanded = expand_symbols(symbols)
    remove_symbols(name, expanded)
    output.render(ActionResult(message=f"Removed {len(expanded)} symbols from {name}"))


@longport_app.command()
def delete(name: str = typer.Argument(help="Longport group name")) -> None:
    """Delete a Longport group."""
    from stk.services.watchlist import delete_group

    delete_group(name)
    output.render(ActionResult(message=f"Deleted group '{name}'"))


@ths_app.command("list")
def ths_list() -> None:
    """List THS groups."""
    from stk.services.ths_wrapper import list_ths_groups

    output.render(list_ths_groups(), meta={"platform": "ths"})


@sync_app.command()
def diff(
    from_group: str = typer.Argument(help="Longport source group"),
    to_group: str | None = typer.Argument(None, help="THS target group"),
) -> None:
    """Compare a Longport group with a THS group without modifying either."""
    from stk.services.sync import compute_diff

    target = to_group or from_group
    output.render(SyncResult(action="diff", diff=compute_diff(from_group, target)))


@sync_app.command()
def push(
    from_group: str = typer.Argument(help="Longport source group"),
    to_group: str | None = typer.Argument(None, help="THS target group"),
    replace: bool = typer.Option(False, "--replace", "-r", help="Replace target contents"),
) -> None:
    """Push a Longport group to THS."""
    from stk.services.sync import push_to_ths

    output.render(push_to_ths(from_group, to_group or from_group, replace=replace))


@sync_app.command()
def pull(
    from_group: str = typer.Argument(help="THS source group"),
    to_group: str | None = typer.Argument(None, help="Longport target group"),
    replace: bool = typer.Option(False, "--replace", "-r", help="Replace target contents"),
) -> None:
    """Pull a THS group into Longport."""
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
    """Refresh current buy and sell signal snapshot groups."""
    if len({src, buy_dst, sell_dst}) != 3:
        raise StkError("Source, buy-signal, and sell-signal groups must be different")

    from stk.services.watchlist import route_signals

    output.render(route_signals(src, buy_dst, sell_dst, replace=replace))
