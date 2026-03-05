"""stk board — sector/concept board commands."""

import typer

from stk import output

app = typer.Typer(help="Sector and concept board data", no_args_is_help=True)


@app.command("list")
def list_boards(
    type: str = typer.Option(
        "sector",
        "--type",
        "-t",
        help="Board type: sector/concept",
    ),
) -> None:
    """List all sector or concept boards with quotes."""
    from stk.services.quote import get_board_list

    result = get_board_list(type=type)
    output.render(result)


@app.command()
def cons(
    name: str = typer.Argument(help="Board name (e.g. 酿酒行业, 人工智能)"),
    type: str = typer.Option(
        "sector",
        "--type",
        "-t",
        help="Board type: sector/concept",
    ),
) -> None:
    """Get constituent stocks of a sector or concept board."""
    from stk.services.quote import get_board_cons

    result = get_board_cons(name, type=type)
    output.render(result)


@app.command()
def flow(
    name: str = typer.Argument(help="Sector or concept name"),
    type: str = typer.Option(
        "sector",
        "--type",
        "-t",
        help="Type: sector/concept",
    ),
) -> None:
    """Get historical fund flow for a sector or concept."""
    from stk.services.flow import get_sector_flow_hist

    result = get_sector_flow_hist(name, type=type)
    output.render(result)


@app.command()
def detail(
    name: str = typer.Argument(help="Sector name"),
    period: str = typer.Option(
        "今日",
        "--period",
        "-p",
        help="Period: 今日/5日/10日",
    ),
) -> None:
    """Get individual stocks' fund flow within a sector."""
    from stk.services.flow import get_sector_flow_detail

    result = get_sector_flow_detail(name, period=period)
    output.render(result)
