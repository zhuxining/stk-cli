"""stk doctor — health check for data sources."""

import typer

from stk import output
from stk.services.health import run_health_check

app = typer.Typer(help="Check data source health", no_args_is_help=True)


@app.command()
def check(
    quick: bool = typer.Option(False, "--quick", "-q", help="Only check critical APIs"),
) -> None:
    """Check all data sources connectivity."""
    results = run_health_check(quick=quick)
    data = [
        {
            "name": r.name,
            "status": r.status,
            "message": r.message,
            "latency_ms": round(r.latency_ms, 2),
        }
        for r in results
    ]
    ok_count = sum(1 for r in results if r.status == "OK")
    output.render(data, meta={"healthy": ok_count, "total": len(results)})
