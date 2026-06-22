"""stk watchlist — watchlist management via longport."""

import typer

from stk import output
from stk.models.common import ActionResult

app = typer.Typer(help="Watchlist management", no_args_is_help=True)


@app.command("list")
def list_all() -> None:
    """List all watchlist groups."""
    from stk.services.watchlist import list_watchlists

    result = list_watchlists()
    output.render(result)


@app.command()
def show(
    name: str = typer.Argument(help="Watchlist group name"),
) -> None:
    """Show securities in a watchlist group."""
    from stk.services.watchlist import get_watchlist

    result = get_watchlist(name)
    output.render(result)


@app.command()
def create(
    name: str = typer.Argument(help="New group name"),
    symbols: list[str] = typer.Option(
        None,
        "--symbol",
        "-s",
        help="Initial symbols",
    ),
) -> None:
    """Create a new watchlist group."""
    from stk.services.watchlist import create_group
    from stk.utils.symbol import expand_symbols

    result = create_group(name, symbols=expand_symbols(symbols) or None)
    output.render(result)


@app.command()
def add(
    name: str = typer.Argument(help="Watchlist group name"),
    symbols: list[str] = typer.Argument(help="One or more symbols to add"),
) -> None:
    """Add symbols to a watchlist group (batch)."""
    from stk.services.watchlist import add_symbols
    from stk.utils.symbol import expand_symbols

    symbols = expand_symbols(symbols)
    add_symbols(name, symbols)
    output.render(ActionResult(message=f"Added {len(symbols)} symbols to {name}"))


@app.command()
def remove(
    name: str = typer.Argument(help="Watchlist group name"),
    symbols: list[str] = typer.Argument(help="One or more symbols to remove"),
) -> None:
    """Remove symbols from a watchlist group (batch)."""
    from stk.services.watchlist import remove_symbols

    remove_symbols(name, symbols)
    output.render(ActionResult(message=f"Removed {len(symbols)} symbols from {name}"))


@app.command()
def delete(
    name: str = typer.Argument(help="Group name to delete"),
) -> None:
    """Delete a watchlist group."""
    from stk.services.watchlist import delete_group

    delete_group(name)
    output.render(ActionResult(message=f"Deleted group '{name}'"))


@app.command()
def scan(
    name: str = typer.Argument(help="Watchlist group name"),
    daily10: bool = typer.Option(
        False,
        "--daily10",
        help="Include recent 10-day compact K-line supplement for focus signals",
    ),
    full_context: bool = typer.Option(
        False,
        "--full-context",
        help="Include neutral/no-signal context factors in scan output",
    ),
) -> None:
    """Daily monitor a watchlist and return focus symbols."""
    from stk.services.scan import scan_watchlist

    result = scan_watchlist(
        name,
        include_daily10=daily10,
        include_full_context=full_context,
    )
    output.render(result, exclude_none=True)


@app.command("scan-live")
def scan_live(
    name: str = typer.Argument(help="Watchlist group name"),
    timeframe: str = typer.Option("15m", "--timeframe", "-t", help="Intraday timeframe: 5m/15m"),
    count: int = typer.Option(80, "--count", "-c", help="Number of intraday bars"),
) -> None:
    """Intraday live scan for a watchlist group."""
    from stk.services.live_scan import scan_live_watchlist

    result = scan_live_watchlist(name, timeframe=timeframe, count=count)
    output.render(result, exclude_none=True)


@app.command()
def kline(
    name: str = typer.Argument(help="Watchlist group name"),
    period: str = typer.Option("day", "--period", "-p", help="Period: day/week/month"),
    count: int = typer.Option(20, "--count", "-c", help="Number of days"),
) -> None:
    """Get K-line + all indicators for every stock in a watchlist group."""
    from stk.services.scan import kline_watchlist

    results = kline_watchlist(name, period=period, count=count)
    output.render(results, meta={"group": name, "count": len(results)})


@app.command()
def scoop(
    name: str = typer.Argument(help="Destination watchlist group name"),
    scan: bool = typer.Option(
        False,
        "--scan",
        help="Scan-filter: only add stocks with 推荐 signal",
    ),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Tighter filters (requires --scan): age<=2 + supportive bias + RR>=1.5",
    ),
    replace: bool = typer.Option(
        False,
        "--replace",
        "-r",
        help="Replace destination instead of appending",
    ),
) -> None:
    """Scoop today's market candidates into a watchlist group."""
    from stk.services.watchlist import scoop_candidates

    result = scoop_candidates(name, do_scan=scan, strict=strict, replace=replace)
    output.render(result)


@app.command()
def hot(
    name: str = typer.Argument(help="Destination watchlist group name"),
    source: str = typer.Option(
        "rank",
        "--source",
        "-s",
        help="Data source: rank (热门排名) / up (热度上升)",
    ),
    scan: bool = typer.Option(
        False,
        "--scan",
        help="Scan-filter: only add stocks with 推荐 signal",
    ),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Tighter filters (requires --scan): age<=2 + supportive bias + RR>=1.5",
    ),
    replace: bool = typer.Option(
        False,
        "--replace",
        "-r",
        help="Replace destination instead of appending",
    ),
) -> None:
    """Fetch hot stocks from EastMoney, scan, and add recommended ones to a group."""
    from stk.services.watchlist import hot_candidates

    result = hot_candidates(name, source=source, do_scan=scan, strict=strict, replace=replace)
    output.render(result)


@app.command()
def route(
    src: str = typer.Argument(help="Source group to scan"),
    entry_dst: str = typer.Argument(help="Destination for entry signals (buy/oversold)"),
    exit_dst: str = typer.Argument(help="Destination for exit signals"),
    replace: bool = typer.Option(
        False,
        "--replace",
        "-r",
        help="Replace destinations instead of appending",
    ),
) -> None:
    """Scan a group and route entry/exit signals to destination groups."""
    from stk.services.watchlist import route_signals

    result = route_signals(src, entry_dst, exit_dst, replace=replace)
    output.render(result)


@app.command()
def zigzag(
    src: str = typer.Argument(help="Source watchlist group"),
    dst: str = typer.Argument(help="Destination group for picks"),
) -> None:
    """Find symbols with a zigzag pivot (high or low) in the last 5 bars."""
    from stk.services.watchlist import zigzag_picks

    result = zigzag_picks(src, dst)
    output.render(result)
