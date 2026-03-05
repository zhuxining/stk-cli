"""stk market — market overview."""

import typer

from stk import output

app = typer.Typer(help="Market indices, temperature, breadth, and news", no_args_is_help=True)


@app.command()
def index() -> None:
    """Get major index quotes."""
    from stk.services.market import get_indices

    result = get_indices()
    output.render(result, meta={"count": len(result)})


@app.command()
def temp() -> None:
    """Get market temperature score (0-100)."""
    from stk.services.market import get_temperature

    result = get_temperature()
    output.render(result)


@app.command()
def breadth() -> None:
    """Get market breadth (advance/decline stats)."""
    from stk.services.market import get_breadth

    result = get_breadth()
    output.render(result)


@app.command("news")
def news_cmd(
    source: str = typer.Option(
        "cls",
        "--source",
        "-s",
        help="Source: cls (财联社) / ths (同花顺) / em (东方财富)",
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
