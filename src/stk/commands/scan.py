"""Longport group signal scanning command."""

import typer

from stk import output


def scan(
    group: str = typer.Argument(help="Longport group name"),
    daily10: bool = typer.Option(
        False,
        "--daily10",
        help="Include recent compact daily bars for focus signals",
    ),
    full_context: bool = typer.Option(
        False,
        "--full-context",
        help="Include neutral and no-signal context factors",
    ),
) -> None:
    """Scan confirmed daily signals for a Longport group."""
    from stk.services.scan import scan_watchlist

    result = scan_watchlist(
        group,
        include_daily10=daily10,
        include_full_context=full_context,
    )
    output.render(result, exclude_none=True)
