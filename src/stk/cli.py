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
from stk.commands import cache, doctor, market, stock, watchlist  # noqa: E402

app.add_typer(market.app, name="market")
app.add_typer(stock.app, name="stock")
app.add_typer(watchlist.app, name="watchlist")
app.add_typer(doctor.app, name="doctor")
app.add_typer(cache.app, name="cache")


def cli() -> None:
    """CLI entry point with global error handling."""
    try:
        app()
    except StkError as e:
        output.render_error(type(e).__name__, e.message)
        raise SystemExit(1) from None
    except Exception as e:
        output.render_error("UnexpectedError", str(e))
        raise SystemExit(1) from None
