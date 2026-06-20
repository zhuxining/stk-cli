"""stk sync — cross-platform watchlist sync commands."""

import typer

from stk import output
from stk.models.sync import SyncResult

app = typer.Typer(help="跨平台自选股同步", no_args_is_help=True)

_THS_HELP = """
同花顺同步命令组。

需要先在 .env 中配置：
  THS_USERNAME=手机号
  THS_PASSWORD=密码
"""

ths_app = typer.Typer(help="同花顺同步", no_args_is_help=True)
app.add_typer(ths_app, name="ths", help=_THS_HELP)


@ths_app.command("list")
def ths_list() -> None:
    """列出同花顺所有自选分组。"""
    from stk.services.ths_wrapper import list_ths_groups

    result = list_ths_groups()
    output.render(result, meta={"platform": "ths"})


@ths_app.command("diff")
def ths_diff(
    from_group: str = typer.Option(
        ..., "--from", "-f", help="长桥自选分组名"
    ),
    to_group: str = typer.Option(
        None, "--to", "-t", help="同花顺分组名（默认与长桥同名）"
    ),
) -> None:
    """对比长桥与同花顺分组的差异（不修改）。"""
    from stk.services.sync import compute_diff

    target = to_group or from_group
    result = compute_diff(from_group, target)
    sync_result = SyncResult(action="diff", diff=result)
    output.render(sync_result)


@ths_app.command("push")
def ths_push(
    from_group: str = typer.Option(
        ..., "--from", "-f", help="长桥自选分组名（源）"
    ),
    to_group: str = typer.Option(
        None, "--to", "-t", help="同花顺分组名（目标，默认与长桥同名）"
    ),
    replace: bool = typer.Option(
        False, "--replace", "-r", help="全量覆盖（清空目标再写入）"
    ),
) -> None:
    """将长桥自选分组推送到同花顺（差异增删）。"""
    from stk.services.sync import push_to_ths

    target = to_group or from_group
    result = push_to_ths(from_group, target, replace=replace)
    output.render(result)
