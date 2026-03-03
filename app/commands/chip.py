"""stk chip — chip distribution (A-share stocks only)."""

import typer

from app import output

app = typer.Typer(help="Chip distribution analysis", no_args_is_help=True)


@app.command()
def cost(
    symbol: str = typer.Argument(help="Stock symbol (e.g. 600519)"),
) -> None:
    """Get chip cost distribution."""
    from app.services.chip import get_chip_distribution

    result = get_chip_distribution(symbol)
    output.render(result)


@app.command()
def holder(
    symbol: str = typer.Argument(help="Stock symbol (e.g. 600519)"),
) -> None:
    """Get shareholder count changes."""
    from app.services.chip import get_holder_change

    result = get_holder_change(symbol)
    output.render(result, meta={"count": len(result)})
