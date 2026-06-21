"""stk scripts — workflow Makefile management."""

from pathlib import Path

import typer

from stk import output
from stk.config import settings
from stk.models.common import ActionResult

app = typer.Typer(help="工作流脚本管理", no_args_is_help=True)

_TEMPLATE = Path(__file__).resolve().parent.parent.parent / "scripts" / "Makefile"


@app.command()
def install() -> None:
    """复制工作流 Makefile 到 ~/.stk/Makefile。"""
    if not _TEMPLATE.exists():
        output.render_error("ConfigError", f"模板文件不存在: {_TEMPLATE}")
        raise SystemExit(1)

    dst = settings.data_dir / "Makefile"
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(_TEMPLATE.read_bytes())

    output.render(
        ActionResult(
            message=f"已安装到 {dst}\n\n"
            f"使用方式:\n"
            f"  make -f ~/.stk/Makefile daily\n"
            f"  make -f ~/.stk/Makefile push GROUP=重点关注\n\n"
            f"快捷别名 (加到 ~/.zshrc):\n"
            f"  alias stk='make -f ~/.stk/Makefile'\n"
            f"  然后: stk daily"
        )
    )


@app.command()
def list() -> None:
    """列出 Makefile 中的可用目标。"""
    target = settings.data_dir / "Makefile"
    if not target.exists():
        output.render_error(
            "ConfigError",
            "~/.stk/Makefile 不存在，请先运行 stk scripts install",
        )
        raise SystemExit(1)

    text = target.read_text()
    targets = []
    for line in text.splitlines():
        if "## " in line and ":" in line:
            name = line.split(":")[0].strip()
            desc = line.split("##")[-1].strip()
            targets.append({"target": name, "description": desc})

    output.render(targets, meta={"file": str(target)})
