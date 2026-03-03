"""stk watchlist — watchlist management."""

import typer

from stk import output

app = typer.Typer(help="Watchlist management", no_args_is_help=True)


@app.command("list")
def list_all() -> None:
    """List all watchlists."""
    from stk.services.watchlist import list_watchlists

    result = list_watchlists()
    output.render(result)


@app.command()
def show(
    name: str = typer.Argument(help="Watchlist name"),
) -> None:
    """Show symbols in a watchlist."""
    from stk.services.watchlist import get_watchlist

    result = get_watchlist(name)
    output.render(result)


@app.command()
def add(
    name: str = typer.Argument(help="Watchlist name"),
    symbol: str = typer.Argument(help="Symbol to add"),
) -> None:
    """Add a symbol to a watchlist."""
    from stk.services.watchlist import add_symbol

    add_symbol(name, symbol)
    output.render({"message": f"Added {symbol} to {name}"})


@app.command()
def remove(
    name: str = typer.Argument(help="Watchlist name"),
    symbol: str = typer.Argument(help="Symbol to remove"),
) -> None:
    """Remove a symbol from a watchlist."""
    from stk.services.watchlist import remove_symbol

    remove_symbol(name, symbol)
    output.render({"message": f"Removed {symbol} from {name}"})
