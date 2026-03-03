"""stk fundamental — financial data."""

import typer

from app import output

app = typer.Typer(help="Fundamental data (financials, valuation, dividends)", no_args_is_help=True)


@app.command()
def report(
    symbol: str = typer.Argument(help="Stock symbol (e.g. 600519)"),
    type: str = typer.Option("income", "--type", "-t", help="Report type: income/balance/cashflow"),
    period: str = typer.Option("latest", "--period", "-p", help="Period (e.g. 2025Q3)"),
) -> None:
    """Get financial report."""
    from app.services.fundamental import get_financial_report

    result = get_financial_report(symbol, report_type=type, period=period)
    output.render(result)


@app.command()
def valuation(
    symbol: str = typer.Argument(help="Stock symbol"),
) -> None:
    """Get valuation metrics (PE, PB, PS, market cap)."""
    from app.services.fundamental import get_valuation

    result = get_valuation(symbol)
    output.render(result)


@app.command()
def dividend(
    symbol: str = typer.Argument(help="Stock symbol"),
) -> None:
    """Get dividend history."""
    from app.services.fundamental import get_dividends

    result = get_dividends(symbol)
    output.render(result, meta={"count": len(result)})
