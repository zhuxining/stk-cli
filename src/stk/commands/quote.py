"""stk quote — real-time quotes."""

import typer

from stk import output
from stk.models.common import TargetType

app = typer.Typer(help="Real-time quote data", no_args_is_help=True)


@app.command()
def get(
    symbol: str = typer.Argument(help="Symbol or name (e.g. 600519, 700.HK)"),
    type: TargetType = typer.Option(TargetType.STOCK, "--type", "-t", help="Target type"),
) -> None:
    """Get real-time quote for a symbol."""
    from stk.services.quote import get_quote

    result = get_quote(symbol, target_type=type)
    output.render(result, meta={"source": "auto"})
