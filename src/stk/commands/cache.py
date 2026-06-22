"""stk cache — cache management commands."""

import typer

from stk import output

app = typer.Typer(help="Cache management", no_args_is_help=True)


@app.command()
def clear(
    prefix: str = typer.Option("", "--prefix", "-p", help="Clear entries matching this prefix"),
) -> None:
    """Clear cached API responses."""
    from stk.store.cache import clear_cache

    count = clear_cache(prefix)
    output.render({"cleared": count, "prefix": prefix or "(all)"})


@app.command()
def stats() -> None:
    """Show cache statistics (memory + disk)."""
    from stk.store.cache import cache_stats

    output.render(cache_stats())
