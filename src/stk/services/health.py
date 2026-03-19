"""Health check service — verify data source connectivity."""

from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class HealthResult:
    """Result of a single health check."""

    name: str
    status: str  # "OK", "FAIL", "WARN"
    message: str
    latency_ms: float = 0.0


def _check_api(name: str, fn: Callable[[], bool], desc: str) -> HealthResult:
    """Check a single API endpoint."""
    import time

    try:
        start = time.perf_counter()
        success = fn()
        latency = (time.perf_counter() - start) * 1000

        if success:
            return HealthResult(name, "OK", f"{desc} 正常", latency)
        else:
            return HealthResult(name, "WARN", f"{desc} 返回空数据", latency)
    except Exception as e:
        error_msg = str(e)
        if "RemoteDisconnected" in error_msg or "closed connection" in error_msg.lower():
            return HealthResult(name, "FAIL", "连接被服务端关闭", 0.0)
        elif "timeout" in error_msg.lower():
            return HealthResult(name, "FAIL", "请求超时", 0.0)
        return HealthResult(name, "FAIL", error_msg[:50], 0.0)


def check_longport() -> HealthResult:
    """Check longport connection."""

    def fn():
        from stk.deps import get_longport_ctx

        ctx = get_longport_ctx()
        return ctx is not None

    return _check_api("longport", fn, "连接")


def run_health_check(*, quick: bool = False) -> list[HealthResult]:
    """Run all health checks."""
    fns = [check_longport]
    return [fn() for fn in fns]
