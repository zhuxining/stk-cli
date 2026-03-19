"""Technical indicator calculation service (ta-lib + pandas)."""

import collections.abc

import numpy as np
import pandas as pd
import talib

from stk.errors import IndicatorError
from stk.models.common import TargetType
from stk.models.indicator import AllIndicatorsResult, DailyResult, IndicatorResult
from stk.services.history import candles_to_df, get_history

_EMA_PERIODS = (5, 10, 20, 60)


def _calc_ema(df: pd.DataFrame, params: dict) -> list[dict]:
    periods = params.get("periods", _EMA_PERIODS)
    emas = {p: talib.EMA(df["close"], timeperiod=p) for p in periods}
    rows: list[dict] = []
    for i, d in enumerate(df["date"]):
        row: dict = {"date": d}
        for p, arr in emas.items():
            v = arr[i]
            row[f"EMA{p}"] = None if np.isnan(v) else round(v, 4)
        rows.append(row)
    return rows


def _calc_macd(df: pd.DataFrame, params: dict) -> list[dict]:
    fast = params.get("fastperiod", 12)
    slow = params.get("slowperiod", 26)
    signal = params.get("signalperiod", 9)
    macd, macd_signal, macd_hist = talib.MACD(
        df["close"], fastperiod=fast, slowperiod=slow, signalperiod=signal
    )
    return [
        {
            "date": d,
            "MACD": None if np.isnan(m) else round(m, 4),
            "signal": None if np.isnan(s) else round(s, 4),
            "hist": None if np.isnan(h) else round(h, 4),
        }
        for d, m, s, h in zip(df["date"], macd, macd_signal, macd_hist, strict=False)
    ]


def _calc_rsi(df: pd.DataFrame, params: dict) -> list[dict]:
    period = params.get("timeperiod", 14)
    result = talib.RSI(df["close"], timeperiod=period)
    return [
        {"date": d, "RSI": None if np.isnan(v) else round(v, 4)}
        for d, v in zip(df["date"], result, strict=False)
    ]


def _calc_kdj(df: pd.DataFrame, params: dict) -> list[dict]:
    fastk_period = params.get("fastk_period", 9)
    slowk_period = params.get("slowk_period", 3)
    slowd_period = params.get("slowd_period", 3)
    k, d = talib.STOCH(
        df["high"],
        df["low"],
        df["close"],
        fastk_period=fastk_period,
        slowk_period=slowk_period,
        slowd_period=slowd_period,
    )
    # J = 3K - 2D
    j = 3 * k - 2 * d
    return [
        {
            "date": dt,
            "K": None if np.isnan(kv) else round(kv, 4),
            "D": None if np.isnan(dv) else round(dv, 4),
            "J": None if np.isnan(jv) else round(jv, 4),
        }
        for dt, kv, dv, jv in zip(df["date"], k, d, j, strict=False)
    ]


def _calc_boll(df: pd.DataFrame, params: dict) -> list[dict]:
    period = params.get("timeperiod", 20)
    nbdev = params.get("nbdevup", 2)
    upper, middle, lower = talib.BBANDS(
        df["close"], timeperiod=period, nbdevup=nbdev, nbdevdn=nbdev
    )
    return [
        {
            "date": d,
            "upper": None if np.isnan(u) else round(u, 4),
            "middle": None if np.isnan(m) else round(m, 4),
            "lower": None if np.isnan(lo) else round(lo, 4),
        }
        for d, u, m, lo in zip(df["date"], upper, middle, lower, strict=False)
    ]


def _calc_atr(df: pd.DataFrame, params: dict) -> list[dict]:
    period = params.get("timeperiod", 14)
    result = talib.ATR(df["high"], df["low"], df["close"], timeperiod=period)
    return [
        {"date": d, f"ATR{period}": None if np.isnan(v) else round(v, 4)}
        for d, v in zip(df["date"], result, strict=False)
    ]


_INDICATOR_MAP: dict[str, collections.abc.Callable] = {
    "EMA": _calc_ema,
    "MACD": _calc_macd,
    "RSI": _calc_rsi,
    "KDJ": _calc_kdj,
    "BOLL": _calc_boll,
    "ATR": _calc_atr,
}


def _fetch_df(
    symbol: str,
    *,
    target_type: TargetType = TargetType.STOCK,
    period: str = "day",
    count: int = 60,
) -> pd.DataFrame:
    """Fetch history and convert to DataFrame (shared by single/all)."""
    candles = get_history(symbol, target_type=target_type, period=period, count=count)
    if not candles:
        raise IndicatorError(f"No history data for {symbol}")
    return candles_to_df(candles)


def calc_indicator(
    symbol: str,
    indicator_name: str,
    *,
    target_type: TargetType = TargetType.STOCK,
    period: str = "day",
    count: int = 60,
    **params,
) -> IndicatorResult:
    """Calculate a single technical indicator for the given symbol."""
    name_upper = indicator_name.upper()
    calc_fn = _INDICATOR_MAP.get(name_upper)
    if calc_fn is None:
        supported = ", ".join(sorted(_INDICATOR_MAP))
        raise IndicatorError(f"Unknown indicator: {indicator_name}. Supported: {supported}")

    df = _fetch_df(symbol, target_type=target_type, period=period, count=count)
    values = calc_fn(df, params)[::-1]

    return IndicatorResult(
        symbol=symbol,
        indicator=name_upper,
        params=params or None,
        values=values,
    )


def calc_all_indicators(
    symbol: str,
    *,
    target_type: TargetType = TargetType.STOCK,
    period: str = "day",
    count: int = 10,
) -> AllIndicatorsResult:
    """Calculate all indicators in one pass (single history fetch).

    Fetches enough history for indicator warm-up, returns only the last *count* rows.
    """
    # MACD(26+9) and BOLL/MA(20) need warm-up; 60 extra bars is sufficient
    warmup = 60
    df = _fetch_df(symbol, target_type=target_type, period=period, count=count + warmup)
    indicators = {name: calc_fn(df, {})[-count:][::-1] for name, calc_fn in _INDICATOR_MAP.items()}
    return AllIndicatorsResult(symbol=symbol, indicators=indicators)


def get_daily(
    symbol: str,
    *,
    target_type: TargetType = TargetType.STOCK,
    period: str = "day",
    count: int = 10,
) -> DailyResult:
    """Get OHLCV + all indicators merged per day (single history fetch)."""
    warmup = 60
    df = _fetch_df(symbol, target_type=target_type, period=period, count=count + warmup)

    # Compute all indicators on full df
    indicator_rows = {name: calc_fn(df, {}) for name, calc_fn in _INDICATOR_MAP.items()}

    # Take last `count` rows, merge OHLCV + indicators per day
    n = len(df)
    days: list[dict] = []
    for i in range(n - count, n):
        row = df.iloc[i]
        day: dict = {
            "date": row["date"],
            "open": round(row["open"], 4),
            "high": round(row["high"], 4),
            "low": round(row["low"], 4),
            "close": round(row["close"], 4),
            "volume": int(row["volume"]),
            "turnover": round(row["turnover"], 4),
        }
        # Change percent
        if i > 0:
            prev_close = df.iloc[i - 1]["close"]
            if prev_close:
                day["change_pct"] = round((row["close"] - prev_close) / prev_close * 100, 2)
        # Merge indicator values (skip date key)
        for values in indicator_rows.values():
            for k, v in values[i].items():
                if k != "date":
                    day[k] = v
        days.append(day)

    days.reverse()
    return DailyResult(symbol=symbol, days=days)
