"""ETF rotation command."""

import typer

from stk import output


def rotate(
    sources: list[str] = typer.Argument(help="Longport ETF source groups"),
) -> None:
    """Rank ETF source pools independently without modifying groups."""
    from stk.services.rotation import rotate_pools

    output.render(rotate_pools(sources))
