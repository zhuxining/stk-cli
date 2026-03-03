"""stk market — market overview."""

import typer

from stk import output

app = typer.Typer(help="Market indices, temperature, and breadth", no_args_is_help=True)


@app.command()
def index() -> None:
    """Get major index quotes."""
    from stk.services.market import get_indices

    result = get_indices()
    output.render(result, meta={"count": len(result)})


@app.command()
def temperature() -> None:
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
