"""stk history — historical candlesticks."""

import typer

from stk import output
from stk.models.common import TargetType

app = typer.Typer(help="Historical K-line data", no_args_is_help=True)


@app.command()
def get(
    symbol: str = typer.Argument(help="Symbol or name"),
    type: TargetType = typer.Option(TargetType.STOCK, "--type", "-t", help="Target type"),
    period: str = typer.Option("day", "--period", "-p", help="Period: day/week/month"),
    count: int = typer.Option(30, "--count", "-c", help="Number of candlesticks"),
) -> None:
    """Get historical candlestick data."""
    from stk.services.history import get_history

    result = get_history(symbol, target_type=type, period=period, count=count)
    output.render(result, meta={"count": len(result)})
