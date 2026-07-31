"""Longport group signal scanning command."""

import typer

from stk import output


def scan(
    group: str = typer.Argument(help="Longport group name"),
    recent_bars: int | None = typer.Option(
        None,
        "--recent-bars",
        min=1,
        max=30,
        help="Attach up to 30 recent confirmed bars to each signal",
    ),
    include_factors: bool = typer.Option(
        False,
        "--include-factors",
        help="Include detailed auxiliary quality factors",
    ),
) -> None:
    """Scan current buy and sell signals for a Longport group."""
    from stk.services.scan import scan_watchlist

    output.render(
        scan_watchlist(
            group,
            recent_bars=recent_bars or 0,
            include_factors=include_factors,
        )
    )
