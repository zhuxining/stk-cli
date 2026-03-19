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
        help="Tech screen: lxsz/cxfl/xstp/ljqs",
    ),
    ma: str = typer.Option(
        "20日均线",
        "--ma",
        help="MA line (xstp only): 5日均线/10日均线/20日均线/60日均线/250日均线",
    ),
) -> None:
    """Technical screening ranking (THS)."""
    from stk.services.rank import get_tech_rank

    result = get_tech_rank(type=screen, ma=ma)
    output.render(result)


@app.command()
def quote(
    symbols: list[str] = typer.Argument(help="One or more symbols (e.g. 600519 700.HK)"),
    type: TargetType = typer.Option(TargetType.STOCK, "--type", "-t", help="Target type"),
) -> None:
    """Get real-time quotes. Accepts multiple symbols in a single call."""
    from stk.services.quote import get_quotes

    results = get_quotes(symbols, target_type=type)
    output.render(results, meta={"source": "auto"})


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
    symbols: list[str] = typer.Argument(help="One or more stock symbols"),
) -> None:
    """Get calc index metrics (PE, PB, market cap, change rates, etc). Accepts multiple symbols."""
    from stk.services.fundamental import get_valuations

    results = get_valuations(symbols)
    output.render(results if len(results) > 1 else results[0])


@app.command()
def indicator(
    symbol: str = typer.Argument(help="Symbol or name"),
    name: str = typer.Argument(None, help="Indicator: EMA/MACD/RSI/KDJ/BOLL/ATR (omit for all)"),
    type: TargetType = typer.Option(TargetType.STOCK, "--type", "-t", help="Target type"),
    period: str = typer.Option("day", "--period", "-p", help="K-line period"),
    count: int = typer.Option(10, "--count", "-c", help="Number of data points"),
    timeperiod: int = typer.Option(None, "--timeperiod", help="Indicator period (e.g. MA20 → 20)"),
) -> None:
    """Calculate technical indicators. Omit name to calculate all at once."""
    if name is None:
        from stk.services.indicator import calc_all_indicators

        result = calc_all_indicators(symbol, target_type=type, period=period, count=count)
    else:
        from stk.services.indicator import calc_indicator

        params = {}
        if timeperiod is not None:
            params["timeperiod"] = timeperiod
        result = calc_indicator(
            symbol, name, target_type=type, period=period, count=count, **params
        )
    output.render(result)


@app.command()
def history(
    symbols: list[str] = typer.Argument(help="One or more symbols"),
    type: TargetType = typer.Option(TargetType.STOCK, "--type", "-t", help="Target type"),
    period: str = typer.Option("day", "--period", "-p", help="Period: day/week/month"),
    count: int = typer.Option(10, "--count", "-c", help="Number of days"),
) -> None:
    """Get OHLCV + all technical indicators (merged per day). Accepts multiple symbols."""
    from stk.services.indicator import get_daily

    results = [get_daily(s, target_type=type, period=period, count=count) for s in symbols]
    output.render(results)


@app.command("flow")
def flow_cmd(
    symbols: list[str] = typer.Argument(help="One or more stock symbols (e.g. 600519 700.HK)"),
) -> None:
    """Get individual stock money flow. Accepts multiple symbols."""
    if len(symbols) == 1:
        from stk.services.flow import get_stock_flow

        result = get_stock_flow(symbols[0])
        output.render(result)
    else:
        from stk.services.flow import get_stock_flows

        results = get_stock_flows(symbols)
        output.render(list(results.values()))


@app.command()
def summary(
    symbols: list[str] = typer.Argument(help="One or more symbols (e.g. 600519 000001 700.HK)"),
) -> None:
    """Batch analysis: quote + score + valuation + flow in one call. Accepts multiple symbols."""
    from stk.services.scan import batch_summary

    result = batch_summary(symbols)
    output.render(result)


@app.command()
def score(
    symbols: list[str] = typer.Argument(help="One or more symbols (e.g. 600519 700.HK)"),
    count: int = typer.Option(60, "--count", "-c", help="History data points for calculation"),
) -> None:
    """Multi-indicator resonance score (RSI+KDJ+MACD+BOLL+volume+flow). Accepts multiple symbols."""
    from stk.services.score import calc_score

    results = [calc_score(s, count=count) for s in symbols]
    output.render(results)
