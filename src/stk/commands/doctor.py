"""stk doctor — health check for data sources."""

import typer

from stk import output
from stk.services.health import HealthResult, run_health_check

app = typer.Typer(help="Check data source health", no_args_is_help=True)


@app.command()
def check(
    quick: bool = typer.Option(False, "--quick", "-q", help="Only check critical APIs"),
    as_json: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """Check all data sources connectivity."""
    results = run_health_check(quick=quick)

    if as_json:
        _render_json(results)
    else:
        _render_text(results)


def _render_text(results: list[HealthResult]) -> None:
    """Render results as human-readable text."""
    print("Checking data sources...\n")

    ok_count = 0
    for r in results:
        if r.status == "OK":
            icon = "✅"
            ok_count += 1
        elif r.status == "WARN":
            icon = "⚠️"
        else:
            icon = "❌"

        status = f"{r.status:<6}"
        print(f"{icon} {r.name:<25} {status}- {r.message}")

    print(f"\nSummary: {ok_count}/{len(results)} sources healthy")


def _render_json(results: list[HealthResult]) -> None:
    """Render results as JSON envelope."""
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
    meta = {"healthy": ok_count, "total": len(results)}

    output.render(data, meta=meta)
