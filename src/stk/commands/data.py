"""Market data commands."""

import typer

from stk import output
from stk.errors import error_code
from stk.models.common import BatchFailure
from stk.models.indicator import KlineBatchResult, KlinePeriod

app = typer.Typer(help="Historical data with technical indicators", no_args_is_help=True)


@app.command()
def kline(
    symbols: list[str] = typer.Argument(help="One or more symbols"),
    period: KlinePeriod = typer.Option(
        KlinePeriod.DAY,
        "--period",
        "-p",
        help="Period: day/week/month",
    ),
    count: int = typer.Option(20, "--count", "-c", min=1, help="Number of bars"),
) -> None:
    """Get OHLCV and all technical indicators for one or more symbols."""
    from stk.services.indicator import get_daily
    from stk.utils.symbol import expand_symbols, to_longport_symbol

    normalized = expand_symbols(symbols)
    series = []
    failures: list[BatchFailure] = []
    for symbol in normalized:
        try:
            series.append(get_daily(symbol, period=period, count=count))
        except Exception as err:
            failures.append(
                BatchFailure(
                    symbol=to_longport_symbol(symbol),
                    code=error_code(err),
                    message=str(err),
                )
            )
    output.render(
        KlineBatchResult(
            period=period,
            requested=len(normalized),
            series=series,
            failures=failures,
        )
    )
