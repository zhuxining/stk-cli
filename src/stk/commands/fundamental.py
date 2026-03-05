"""stk fundamental — financial data."""

import typer

from stk import output

app = typer.Typer(help="Fundamental data (industry comparison, valuation)", no_args_is_help=True)


@app.command()
def compare(
    symbol: str = typer.Argument(help="Stock symbol (e.g. 600519)"),
    type: str = typer.Option("growth", "--type", "-t", help="Category: growth/valuation/dupont"),
) -> None:
    """Get industry comparison (growth, valuation, or DuPont analysis)."""
    from stk.services.fundamental import get_comparison

    result = get_comparison(symbol, category=type)
    output.render(result)


@app.command()
def valuation(
    symbol: str = typer.Argument(help="Stock symbol"),
) -> None:
    """Get valuation metrics (PE, PB, PS, market cap)."""
    from stk.services.fundamental import get_valuation

    result = get_valuation(symbol)
    output.render(result)
