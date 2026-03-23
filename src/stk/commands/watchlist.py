"""stk watchlist — watchlist management via longport."""

import typer

from stk import output
from stk.models.common import ActionResult

app = typer.Typer(help="Watchlist management", no_args_is_help=True)


@app.command("list")
def list_all() -> None:
    """List all watchlist groups."""
    from stk.services.watchlist import list_watchlists

    result = list_watchlists()
    output.render(result)


@app.command()
def show(
    name: str = typer.Argument(help="Watchlist group name"),
) -> None:
    """Show securities in a watchlist group."""
    from stk.services.watchlist import get_watchlist

    result = get_watchlist(name)
    output.render(result)


@app.command()
def create(
    name: str = typer.Argument(help="New group name"),
    symbols: list[str] = typer.Option(
        None,
        "--symbol",
        "-s",
        help="Initial symbols",
    ),
) -> None:
    """Create a new watchlist group."""
    from stk.services.watchlist import create_group

    result = create_group(name, symbols=symbols or None)
    output.render(result)


@app.command()
def add(
    name: str = typer.Argument(help="Watchlist group name"),
    symbol: str = typer.Argument(help="Symbol to add"),
) -> None:
    """Add a symbol to a watchlist group."""
    from stk.services.watchlist import add_symbol

    add_symbol(name, symbol)
    output.render(ActionResult(message=f"Added {symbol} to {name}"))


@app.command()
def remove(
    name: str = typer.Argument(help="Watchlist group name"),
    symbol: str = typer.Argument(help="Symbol to remove"),
) -> None:
    """Remove a symbol from a watchlist group."""
    from stk.services.watchlist import remove_symbol

    remove_symbol(name, symbol)
    output.render(ActionResult(message=f"Removed {symbol} from {name}"))


@app.command()
def delete(
    name: str = typer.Argument(help="Group name to delete"),
) -> None:
    """Delete a watchlist group."""
    from stk.services.watchlist import delete_group

    delete_group(name)
    output.render(ActionResult(message=f"Deleted group '{name}'"))


@app.command()
def scan(
    name: str = typer.Argument(help="Watchlist group name"),
    sort: str = typer.Option("change_pct", "--sort", "-s", help="Sort by: change_pct / score"),
) -> None:
    """Batch scan a watchlist: quote + score all members in one call, sorted by change."""
    from stk.services.scan import scan_watchlist

    result = scan_watchlist(name, sort=sort)
    output.render(result)


@app.command()
def kline(
    name: str = typer.Argument(help="Watchlist group name"),
    period: str = typer.Option("day", "--period", "-p", help="Period: day/week/month"),
    count: int = typer.Option(10, "--count", "-c", help="Number of days"),
) -> None:
    """Get K-line + all indicators for every stock in a watchlist group."""
    from stk.services.scan import kline_watchlist

    results = kline_watchlist(name, period=period, count=count)
    output.render(results, meta={"group": name, "count": len(results)})
