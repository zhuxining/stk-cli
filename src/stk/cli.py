"""Root Typer app — registers all subcommand groups."""

import re
import sys

from loguru import logger
import typer

from stk import output
from stk.config import settings
from stk.errors import StkError, error_code

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
def _callback(
    no_cache: bool = typer.Option(
        False,
        "--no-cache",
        help="Skip all caches — fetch fresh data from APIs",
    ),
) -> None:
    """Stk — Stock Query CLI for Agents."""
    _setup_logging()
    if no_cache:
        from stk.store.cache import disable

        disable()


# Register public routes after the root callback is defined.
from stk.commands import data, group, rotate, scan  # ruff: ignore[module-import-not-at-top-of-file]

app.add_typer(data.app, name="data")
app.add_typer(group.app, name="group")
app.command("scan")(scan.scan)
app.command("rotate")(rotate.rotate)


def cli() -> None:
    """CLI entry point with global error handling."""
    try:
        app()
    except StkError as e:
        output.render_error(error_code(e), e.message)
        raise SystemExit(1) from None
    except Exception as e:
        output.render_error("unexpected_error", str(e))
        raise SystemExit(1) from None
