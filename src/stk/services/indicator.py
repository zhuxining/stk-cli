"""Technical indicator calculation service (ta-lib + pandas)."""

import collections.abc

import numpy as np
import pandas as pd
import talib

from stk.errors import IndicatorError
from stk.models.common import TargetType
from stk.models.indicator import IndicatorResult
from stk.services.history import candles_to_df, get_history


def _calc_ma(df: pd.DataFrame, params: dict) -> list[dict]:
    period = params.get("timeperiod", 20)
    result = talib.SMA(df["close"], timeperiod=period)
    return [
        {"date": d, f"MA{period}": None if np.isnan(v) else round(v, 4)}
        for d, v in zip(df["date"], result, strict=False)
    ]


def _calc_ema(df: pd.DataFrame, params: dict) -> list[dict]:
    period = params.get("timeperiod", 20)
    result = talib.EMA(df["close"], timeperiod=period)
    return [
        {"date": d, f"EMA{period}": None if np.isnan(v) else round(v, 4)}
        for d, v in zip(df["date"], result, strict=False)
    ]


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
    "MA": _calc_ma,
    "EMA": _calc_ema,
    "MACD": _calc_macd,
    "RSI": _calc_rsi,
    "KDJ": _calc_kdj,
    "BOLL": _calc_boll,
    "ATR": _calc_atr,
}


def calc_indicator(
    symbol: str,
    indicator_name: str,
    *,
    target_type: TargetType = TargetType.STOCK,
    period: str = "day",
    count: int = 60,
    **params,
) -> IndicatorResult:
    """Calculate a technical indicator for the given symbol."""
    name_upper = indicator_name.upper()
    calc_fn = _INDICATOR_MAP.get(name_upper)
    if calc_fn is None:
        supported = ", ".join(sorted(_INDICATOR_MAP))
        raise IndicatorError(f"Unknown indicator: {indicator_name}. Supported: {supported}")

    candles = get_history(symbol, target_type=target_type, period=period, count=count)
    if not candles:
        raise IndicatorError(f"No history data for {symbol}")

    df = candles_to_df(candles)
    values = calc_fn(df, params)

    return IndicatorResult(
        symbol=symbol,
        indicator=name_upper,
        params=params or None,
        values=values,
    )
