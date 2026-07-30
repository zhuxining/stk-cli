"""Market data commands."""

import typer

from stk import output

app = typer.Typer(help="Historical data with technical indicators", no_args_is_help=True)


@app.command()
def kline(
    symbols: list[str] = typer.Argument(help="One or more symbols"),
    period: str = typer.Option("day", "--period", "-p", help="Period: day/week/month"),
    count: int = typer.Option(20, "--count", "-c", min=1, help="Number of bars"),
) -> None:
    """Get OHLCV and all technical indicators for one or more symbols."""
    from stk.services.indicator import get_daily
    from stk.utils.symbol import expand_symbols

    normalized = expand_symbols(symbols)
    results = [get_daily(symbol, period=period, count=count) for symbol in normalized]
    output.render(results)
