"""stk market — market overview."""

import typer

from stk import output

app = typer.Typer(help="Market overview and news", invoke_without_command=True)


@app.callback()
def market_overview(ctx: typer.Context) -> None:
    """Get market overview: indices grouped by region + temperature."""
    if ctx.invoked_subcommand is not None:
        return

    from stk.services.market import get_market_overview

    result = get_market_overview()
    output.render(result)


@app.command("news")
def news_cmd(
    source: str = typer.Option(
        "cls",
        "--source",
        "-s",
        help="Source: cls (财联社) / ths (同花顺)",
    ),
    count: int = typer.Option(20, "--count", "-c", help="Number of items"),
    filter_: str = typer.Option(
        "全部",
        "--filter",
        "-f",
        help="Filter (cls only): 全部/重点",
    ),
) -> None:
    """Get global market news."""
    from stk.services.news import get_global_news

    result = get_global_news(source=source, count=count, filter_=filter_)
    output.render(result, meta={"count": len(result), "source": source})
