"""stk flow — money flow."""

import typer

from app import output
from app.models.common import TargetType

app = typer.Typer(help="Money flow data", no_args_is_help=True)


@app.command()
def get(
    symbol: str = typer.Argument(help="Symbol or sector name"),
    type: TargetType = typer.Option(TargetType.STOCK, "--type", "-t", help="Target type"),
) -> None:
    """Get money flow data."""
    from app.services.flow import get_flow

    result = get_flow(symbol, target_type=type)
    output.render(result)
