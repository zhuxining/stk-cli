"""stk stock — individual stock commands."""

import typer

from stk import output
from stk.models.common import TargetType

app = typer.Typer(help="Individual stock data and analysis", no_args_is_help=True)


@app.command()
def rank(
    type: str = typer.Option("hot", "--type", "-t", help="Rank type: hot/tech/flow"),
    # tech-specific
    screen: str = typer.Option(
        "lxsz",
        "--screen",
        "-s",
        help="Tech screen: lxsz/cxfl/xstp/ljqs",
    ),
    ma: str = typer.Option(
        "20日均线",
        "--ma",
        help="MA line (xstp only): 5日均线/10日均线/20日均线/60日均线/250日均线",
    ),
    # flow-specific
    scope: str = typer.Option(
        "stock",
        "--scope",
        help="Flow scope: stock/main/sector/concept",
    ),
    period: str = typer.Option(
        "今日",
        "--period",
        "-p",
        help="Flow period: 今日/3日/5日/10日",
    ),
    market: str = typer.Option(
        "全部股票",
        "--market",
        "-m",
        help="Market filter (flow main scope only)",
    ),
) -> None:
    """Unified ranking: hot stocks, technical screening, or fund flow ranking."""
    if type == "hot":
        from stk.services.rank import get_hot_rank

        result = get_hot_rank()
    elif type == "tech":
        from stk.services.rank import get_tech_rank

        result = get_tech_rank(type=screen, ma=ma)
    elif type == "flow":
        from stk.services.flow import get_flow_rank

        result = get_flow_rank(scope=scope, period=period, market=market)
    else:
        raise typer.BadParameter(f"Unknown rank type: {type}")
    output.render(result)


@app.command()
def quote(
    symbol: str = typer.Argument(help="Symbol or name (e.g. 600519, 700.HK)"),
    type: TargetType = typer.Option(TargetType.STOCK, "--type", "-t", help="Target type"),
) -> None:
    """Get real-time quote for a symbol."""
    from stk.services.quote import get_quote

    result = get_quote(symbol, target_type=type)
    output.render(result, meta={"source": "auto"})


@app.command()
def profile(
    symbol: str = typer.Argument(help="Stock symbol (e.g. 600519)"),
) -> None:
    """Get company main business profile."""
    from stk.services.fundamental import get_profile

    result = get_profile(symbol)
    output.render(result)


@app.command()
def fundamental(
    symbol: str = typer.Argument(help="Stock symbol (e.g. 600519, 700.HK)"),
    type: str = typer.Option(
        "growth",
        "--type",
        "-t",
        help="Category: growth/valuation (A-share also: dupont)",
    ),
) -> None:
    """Get industry comparison (growth, valuation, or DuPont analysis)."""
    from stk.services.fundamental import get_comparison

    result = get_comparison(symbol, category=type)
    output.render(result)


@app.command()
def valuation(
    symbol: str = typer.Argument(help="Stock symbol"),
) -> None:
    """Get valuation metrics (PE, PB, PS, market cap)."""
    from stk.services.fundamental import get_valuation

    result = get_valuation(symbol)
    output.render(result)


@app.command()
def indicator(
    symbol: str = typer.Argument(help="Symbol or name"),
    name: str = typer.Argument(help="Indicator name (e.g. MA, MACD, RSI, KDJ, BOLL)"),
    type: TargetType = typer.Option(TargetType.STOCK, "--type", "-t", help="Target type"),
    period: str = typer.Option("day", "--period", "-p", help="K-line period"),
    count: int = typer.Option(60, "--count", "-c", help="Number of data points"),
) -> None:
    """Calculate a technical indicator."""
    from stk.services.indicator import calc_indicator

    result = calc_indicator(symbol, name, target_type=type, period=period, count=count)
    output.render(result)


@app.command()
def history(
    symbol: str = typer.Argument(help="Symbol or name"),
    type: TargetType = typer.Option(TargetType.STOCK, "--type", "-t", help="Target type"),
    period: str = typer.Option("day", "--period", "-p", help="Period: day/week/month"),
    count: int = typer.Option(30, "--count", "-c", help="Number of candlesticks"),
) -> None:
    """Get historical candlestick data."""
    from stk.services.history import get_history

    result = get_history(symbol, target_type=type, period=period, count=count)
    output.render(result, meta={"count": len(result)})


@app.command("news")
def news_cmd(
    symbol: str = typer.Argument(help="Stock symbol (e.g. 600519)"),
    count: int = typer.Option(10, "--count", "-c", help="Number of items"),
) -> None:
    """List recent news for an individual stock."""
    from stk.services.news import get_news

    result = get_news(symbol, count=count)
    output.render(result, meta={"count": len(result)})


@app.command("flow")
def flow_cmd(
    symbol: str = typer.Argument(help="Stock symbol (e.g. 600519, 700.HK)"),
) -> None:
    """Get individual stock money flow (realtime + recent history)."""
    from stk.services.flow import get_stock_flow

    result = get_stock_flow(symbol)
    output.render(result)


@app.command()
def chip(
    symbol: str = typer.Argument(help="Stock symbol (e.g. 600519)"),
) -> None:
    """Get chip cost distribution."""
    from stk.services.chip import get_chip_distribution

    result = get_chip_distribution(symbol)
    output.render(result)
