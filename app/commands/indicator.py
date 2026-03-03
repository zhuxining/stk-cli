"""stk indicator — technical indicators."""

import typer

from app import output
from app.models.common import TargetType

app = typer.Typer(help="Technical indicators (ta-lib)", no_args_is_help=True)


@app.command()
def get(
    symbol: str = typer.Argument(help="Symbol or name"),
    name: str = typer.Argument(help="Indicator name (e.g. MA, MACD, RSI, KDJ, BOLL)"),
    type: TargetType = typer.Option(TargetType.STOCK, "--type", "-t", help="Target type"),
    period: str = typer.Option("day", "--period", "-p", help="K-line period"),
    count: int = typer.Option(60, "--count", "-c", help="Number of data points"),
) -> None:
    """Calculate a technical indicator."""
    from app.services.indicator import calc_indicator

    result = calc_indicator(symbol, name, target_type=type, period=period, count=count)
    output.render(result)
