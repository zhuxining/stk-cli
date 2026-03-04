"""Root Typer app — registers all subcommand groups."""

import sys

from loguru import logger
import typer

from stk import output
from stk.config import settings
from stk.errors import StkError

app = typer.Typer(
    name="stk",
    help="Stock Query CLI for Agents",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)


def _setup_logging() -> None:
    logger.remove()
    logger.add(sink=sys.stderr, level=settings.log_level)


@app.callback()
def _callback() -> None:
    """Stk — Stock Query CLI for Agents."""
    _setup_logging()


# Register subcommand groups
from stk.commands import (  # noqa: E402
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


def cli() -> None:
    """CLI entry point with global error handling."""
    try:
        app()
    except StkError as e:
        output.render_error(type(e).__name__, e.message)
    except Exception as e:
        output.render_error("UnexpectedError", str(e))
