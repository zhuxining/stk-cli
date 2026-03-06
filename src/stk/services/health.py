"""Health check service — verify data source connectivity."""

from collections.abc import Callable
from dataclasses import dataclass

import akshare as ak


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


def check_akshare_eastmoney() -> HealthResult:
    """Check akshare eastmoney board API."""

    def fn():
        df = ak.stock_board_industry_name_em()
        return not df.empty

    return _check_api("akshare (eastmoney)", fn, "行业板块 API")


def check_akshare_push2() -> HealthResult:
    """Check akshare push2 API (market fund flow)."""

    def fn():
        df = ak.stock_market_fund_flow()
        return not df.empty

    return _check_api("akshare (push2)", fn, "市场资金流 API")


def check_akshare_news() -> HealthResult:
    """Check akshare news API."""

    def fn():
        df = ak.stock_news_em(symbol="000001")
        return not df.empty

    return _check_api("akshare (news)", fn, "新闻 API")


def check_longport() -> HealthResult:
    """Check longport connection."""

    def fn():
        from stk.deps import get_longport_ctx

        ctx = get_longport_ctx()
        return ctx is not None

    return _check_api("longport", fn, "连接")


def run_health_check(*, quick: bool = False) -> list[HealthResult]:
    """
    Run all health checks.

    Args:
        quick: If True, only check critical APIs (eastmoney + longport)

    """
    fns = (
        [check_akshare_eastmoney, check_longport]
        if quick
        else [check_akshare_eastmoney, check_akshare_push2, check_akshare_news, check_longport]
    )
    return [fn() for fn in fns]
