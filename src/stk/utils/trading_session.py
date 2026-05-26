"""Trading session helpers for daily bar confirmation."""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pandas as pd

from stk.utils.symbol import to_longport_symbol

_CN_TZ = ZoneInfo("Asia/Shanghai")
_HK_TZ = ZoneInfo("Asia/Hong_Kong")
_US_TZ = ZoneInfo("America/New_York")


def market_daily_cutoff(symbol: str) -> tuple[ZoneInfo, time]:
    """Return the local timezone and daily-bar confirmation cutoff."""
    lp_symbol = to_longport_symbol(symbol).upper()
    if lp_symbol.endswith((".SH", ".SZ", ".BJ")):
        return _CN_TZ, time(15, 15)
    if lp_symbol.endswith(".HK"):
        return _HK_TZ, time(16, 20)
    if lp_symbol.endswith(".US"):
        return _US_TZ, time(16, 15)
    return _CN_TZ, time(16, 0)


def daily_bar_date(value: object, tz: ZoneInfo) -> date | None:
    timestamp = pd.to_datetime(str(value), errors="coerce")
    if pd.isna(timestamp):
        return None
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert(tz)
    return timestamp.date()


def is_unclosed_daily_bar(
    value: object,
    symbol: str,
    *,
    now: datetime | None = None,
) -> bool:
    """Whether a daily bar belongs to today's still-open session."""
    tz, cutoff = market_daily_cutoff(symbol)
    current = now or datetime.now(tz)
    current = current.astimezone(tz) if current.tzinfo else current.replace(tzinfo=tz)
    return daily_bar_date(value, tz) == current.date() and current.time() < cutoff
