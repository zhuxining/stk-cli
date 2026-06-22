"""stk market — market overview & technical screening."""

import typer

from stk import output

app = typer.Typer(help="Market overview & technical screening")


@app.command()
def index() -> None:
    """Major indices: CN (SSE/SZSE/ChiNext) + HK (HSI) + US (DJI/IXIC/SPX)."""
    from stk.services.market import get_market_overview

    result = get_market_overview()
    output.render(result)


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
    """Cross-screen candidates: stocks appearing in 3+ bull screens,
    no bear screen overlap (THS)."""
    from stk.services.rank import get_tech_candidates

    output.render(get_tech_candidates(ma=ma))


@app.command()
def hotstock(
    source: str = typer.Option(
        "rank",
        "--source",
        "-s",
        help="Data source: rank (热门排名) / up (热度上升)",
    ),
) -> None:
    """Hot stock rankings from 东方财富 (EastMoney).

    - rank: 热门个股排名 (stock_hot_rank_em)
    - up: 热度上升榜 (stock_hot_up_em)
    """
    from stk.services.market import get_hot_rank, get_hot_up

    source_lower = source.lower()
    result = get_hot_up() if source_lower == "up" else get_hot_rank()
    output.render(result)
