"""Technical indicator calculation service (ta-lib + pandas)."""

import collections.abc
import operator

import numpy as np
import pandas as pd
import talib

from stk.errors import IndicatorError
from stk.models.common import TargetType
from stk.models.indicator import DailyResult
from stk.services.history import candles_to_df, get_history

_EMA_PERIODS = (5, 9, 10, 20, 26, 60)


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


def _calc_supertrend_arrays(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    *,
    period: int = 10,
    multiplier: float = 2.5,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Core Supertrend calculation returning (supertrend, direction, atr) arrays."""
    atr = talib.ATR(high, low, close, timeperiod=period)
    hl2 = (high + low) / 2
    basic_upper = hl2 + multiplier * atr
    basic_lower = hl2 - multiplier * atr

    n = len(close)
    final_upper = np.full(n, np.nan)
    final_lower = np.full(n, np.nan)
    supertrend = np.full(n, np.nan)
    direction = np.zeros(n, dtype=int)

    for i in range(n):
        if np.isnan(atr[i]):
            continue

        if i == 0 or np.isnan(final_upper[i - 1]) or np.isnan(final_lower[i - 1]):
            final_upper[i] = basic_upper[i]
            final_lower[i] = basic_lower[i]
            direction[i] = 1
            supertrend[i] = final_lower[i]
            continue

        prev_close = close[i - 1]
        prev_upper = final_upper[i - 1]
        prev_lower = final_lower[i - 1]

        final_upper[i] = (
            basic_upper[i] if basic_upper[i] < prev_upper or prev_close > prev_upper else prev_upper
        )
        final_lower[i] = (
            basic_lower[i] if basic_lower[i] > prev_lower or prev_close < prev_lower else prev_lower
        )

        prev_direction = direction[i - 1] or 1
        if prev_direction == -1 and close[i] > final_upper[i]:
            direction[i] = 1
        elif prev_direction == 1 and close[i] < final_lower[i]:
            direction[i] = -1
        else:
            direction[i] = prev_direction

        supertrend[i] = final_lower[i] if direction[i] == 1 else final_upper[i]

    return supertrend, direction, atr


def _calc_supertrend(df: pd.DataFrame, params: dict) -> list[dict]:
    """Supertrend indicator for daily output (uses shared core calculation)."""
    period = params.get("timeperiod", 10)
    multiplier = params.get("multiplier", 2.5)
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    close = df["close"].to_numpy(dtype=float)

    supertrend, direction, atr = _calc_supertrend_arrays(
        high, low, close, period=period, multiplier=multiplier
    )

    rows: list[dict] = []
    for d, st, trend, atr_value in zip(df["date"], supertrend, direction, atr, strict=False):
        trend_name = "bullish" if trend > 0 else "bearish" if trend < 0 else None
        rows.append({
            "date": d,
            "Supertrend": None if np.isnan(st) else round(float(st), 4),
            "SupertrendDirection": trend_name,
            f"ATR{period}": None if np.isnan(atr_value) else round(float(atr_value), 4),
        })
    return rows


_INDICATOR_MAP: dict[str, collections.abc.Callable] = {
    "EMA": _calc_ema,
    "MACD": _calc_macd,
    "RSI": _calc_rsi,
    "KDJ": _calc_kdj,
    "BOLL": _calc_boll,
    "ATR": _calc_atr,
    "SUPERTREND": _calc_supertrend,
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


def get_daily(
    symbol: str,
    *,
    target_type: TargetType = TargetType.STOCK,
    period: str = "day",
    count: int = 10,
) -> DailyResult:
    """Get OHLCV + all indicators merged per day (single history fetch)."""
    warmup = 50
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
        for indicator_values in indicator_rows.values():
            day_data = indicator_values[i]
            for key, value in day_data.items():
                if key != "date":
                    day[key] = value
        days.append(day)

    days.reverse()
    return DailyResult(symbol=symbol, days=days)


def zigzag_pivots(
    highs: list[float],
    lows: list[float],
    *,
    legs: int = 6,
    pct: float = 3.0,
) -> list[dict]:
    """Detect zigzag pivot points using TradingView's algorithm.

    Pivot detection uses a lookback window (legs) rather than adjacent bars:
    - A pivot high requires the bar's high to be the highest in the window.
    - A pivot low requires the bar's low to be the lowest in the window.
    - Constructs zigzag by connecting alternating pivots with a minimum
      reversal percentage.

    Args:
        highs: High prices, most recent last.
        lows: Low prices, most recent last.
        legs: Total bars to confirm a pivot (divided by 2 for left/right).
              Default 6 (3 bars each side).
        pct: Minimum reversal %% to register a pivot. Default 3.0.

    Returns:
        Pivots from earliest to latest: [{index, price, type}].
    """
    n = len(highs)
    if n < legs:
        return []

    half = legs // 2

    # Step 1: Find all confirmed pivot highs and lows
    pivot_highs: list[dict] = []
    pivot_lows: list[dict] = []

    for i in range(half, n - half):
        left_high = max(highs[i - half : i])
        right_high = max(highs[i + 1 : i + half + 1])
        if highs[i] > left_high and highs[i] >= right_high:
            pivot_highs.append({"index": i, "price": highs[i], "type": "high"})

        left_low = min(lows[i - half : i])
        right_low = min(lows[i + 1 : i + half + 1])
        if lows[i] < left_low and lows[i] <= right_low:
            pivot_lows.append({"index": i, "price": lows[i], "type": "low"})

    # Step 2: Merge by index and construct zigzag
    all_pivots = sorted(pivot_highs + pivot_lows, key=operator.itemgetter("index"))
    if not all_pivots:
        return []

    result = [all_pivots[0]]
    for pivot in all_pivots[1:]:
        last = result[-1]

        if pivot["type"] == last["type"]:
            # Same direction: keep more extreme (higher high / lower low)
            if (pivot["type"] == "high" and pivot["price"] > last["price"]) or (
                pivot["type"] == "low" and pivot["price"] < last["price"]
            ):
                result[-1] = pivot
        else:
            # Opposite direction: check reversal percentage
            chg = (
                (last["price"] - pivot["price"]) / last["price"] * 100
                if last["type"] == "high"
                else (pivot["price"] - last["price"]) / last["price"] * 100
            )
            if chg >= pct:
                result.append(pivot)

    return result
