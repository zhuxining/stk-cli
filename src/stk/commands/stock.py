"""stk stock — individual stock commands."""

import typer

from stk import output
from stk.models.common import TargetType

app = typer.Typer(help="Individual stock data and analysis", no_args_is_help=True)


@app.command()
def rank(
    screen: str = typer.Option(
        "lxsz",
        "--screen",
        "-s",
        help="Tech screen: lxsz/cxfl/xstp/ljqs/cxsl/lxxd/xxtp/ljqd",
    ),
    ma: str = typer.Option(
        "20日均线",
        "--ma",
        help="MA line (xstp/xxtp only): 5日均线/10日均线/20日均线/60日均线/250日均线",
    ),
) -> None:
    """Single tech screen ranking (THS)."""
    from stk.services.rank import get_tech_rank

    output.render(get_tech_rank(type=screen, ma=ma))


@app.command()
def hotspot(
    ma: str = typer.Option(
        "20日均线",
        "--ma",
        help="MA line for xstp/xxtp: 5日均线/10日均线/20日均线/60日均线/250日均线",
    ),
) -> None:
    """Industry sentiment: bull/bear screen counts per industry (THS)."""
    from stk.services.rank import get_tech_industries

    output.render(get_tech_industries(ma=ma))


@app.command()
def candidates(
    ma: str = typer.Option(
        "20日均线",
        "--ma",
        help="MA line for xstp/xxtp: 5日均线/10日均线/20日均线/60日均线/250日均线",
    ),
) -> None:
    """Cross-screen candidates: stocks appearing in 2+ bull screens (THS)."""
    from stk.services.rank import get_tech_candidates

    output.render(get_tech_candidates(ma=ma))


@app.command()
def fundamental(
    symbol: str = typer.Argument(help="Stock symbol (e.g. 600519, 700.HK)"),
    type: str = typer.Option(
        "all",
        "--type",
        "-t",
        help="Category: all/growth/valuation (A-share also: dupont)",
    ),
) -> None:
    """Industry comparison. Default: all categories."""
    if type == "all":
        from stk.services.fundamental import get_full_comparison

        result = get_full_comparison(symbol)
    else:
        from stk.services.fundamental import get_comparison

        result = get_comparison(symbol, category=type)
    output.render(result)


@app.command()
def scan(
    symbols: list[str] = typer.Argument(help="One or more symbols (e.g. 600519 000001 700.HK)"),
    daily10: bool = typer.Option(
        False,
        "--daily10",
        help="Include recent 10-day compact K-line supplement for strong signals",
    ),
    full_context: bool = typer.Option(
        False,
        "--full-context",
        help="Include neutral/no-signal context factors in scan output",
    ),
) -> None:
    """Daily monitor symbols and return focus candidates."""
    from stk.services.scan import batch_summary
    from stk.utils.symbol import expand_symbols

    result = batch_summary(
        expand_symbols(symbols),
        include_daily10=daily10,
        include_full_context=full_context,
    )
    output.render(result, exclude_none=True)


@app.command("scan-live")
def scan_live(
    symbols: list[str] = typer.Argument(help="One or more symbols (e.g. 600519 000001 700.HK)"),
    timeframe: str = typer.Option("15m", "--timeframe", "-t", help="Intraday timeframe: 5m/15m"),
    count: int = typer.Option(80, "--count", "-c", help="Number of intraday bars"),
) -> None:
    """Intraday live scan using daily signal background and minute-bar triggers."""
    from stk.services.live_scan import live_summary
    from stk.utils.symbol import expand_symbols

    result = live_summary(expand_symbols(symbols), timeframe=timeframe, count=count)
    output.render(result, exclude_none=True)


@app.command()
def kline(
    symbols: list[str] = typer.Argument(help="One or more symbols"),
    type: TargetType = typer.Option(TargetType.STOCK, "--type", "-t", help="Target type"),
    period: str = typer.Option("day", "--period", "-p", help="Period: day/week/month"),
    count: int = typer.Option(20, "--count", "-c", help="Number of days"),
) -> None:
    """Get OHLCV + all technical indicators (merged per day). Accepts multiple symbols."""
    from stk.services.indicator import get_daily

    results = [get_daily(s, target_type=type, period=period, count=count) for s in symbols]
    output.render(results)
