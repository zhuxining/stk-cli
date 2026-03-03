"""Root Typer app — registers all subcommand groups."""

from loguru import logger
import typer

from app.config import settings

app = typer.Typer(
    name="stk",
    help="Stock Query CLI for Agents",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)


def _setup_logging() -> None:
    logger.remove()
    logger.add(
        sink=lambda msg: print(msg, end="", file=__import__("sys").stderr),
        level=settings.log_level,
    )


@app.callback()
def main() -> None:
    """stk — Stock Query CLI for Agents."""
    _setup_logging()


# Register subcommand groups
from app.commands import (  # noqa: E402
    chip,
    flow,
    fundamental,
    history,
    indicator,
    market,
    news,
    quote,
    watchlist,
)

app.add_typer(quote.app, name="quote")
app.add_typer(history.app, name="history")
app.add_typer(indicator.app, name="indicator")
app.add_typer(news.app, name="news")
app.add_typer(fundamental.app, name="fundamental")
app.add_typer(market.app, name="market")
app.add_typer(flow.app, name="flow")
app.add_typer(chip.app, name="chip")
app.add_typer(watchlist.app, name="watchlist")
