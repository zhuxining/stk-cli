"""stk chip — chip distribution (A-share stocks only)."""

import typer

from stk import output

app = typer.Typer(help="Chip distribution analysis", no_args_is_help=True)


@app.command()
def cost(
    symbol: str = typer.Argument(help="Stock symbol (e.g. 600519)"),
) -> None:
    """Get chip cost distribution."""
    from stk.services.chip import get_chip_distribution

    result = get_chip_distribution(symbol)
    output.render(result)
