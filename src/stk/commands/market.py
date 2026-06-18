"""stk market — market overview."""

import typer

from stk import output

app = typer.Typer(help="Market overview", invoke_without_command=True)


@app.callback()
def market_overview(ctx: typer.Context) -> None:
    """Get market overview: indices grouped by region + temperature."""
    if ctx.invoked_subcommand is not None:
        return

    from stk.services.market import get_market_overview

    result = get_market_overview()
    output.render(result)
