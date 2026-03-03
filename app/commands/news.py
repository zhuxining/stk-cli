"""stk news — news feed."""

import typer

from app import output
from app.models.common import TargetType

app = typer.Typer(help="News and announcements", no_args_is_help=True)


@app.command()
def list(
    symbol: str = typer.Argument(help="Symbol or name"),
    type: TargetType = typer.Option(TargetType.STOCK, "--type", "-t", help="Target type"),
    count: int = typer.Option(10, "--count", "-c", help="Number of news items"),
) -> None:
    """List recent news for a symbol."""
    from app.services.news import get_news

    result = get_news(symbol, target_type=type, count=count)
    output.render(result, meta={"count": len(result)})
