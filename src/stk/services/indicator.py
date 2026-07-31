"""Technical indicator calculation service (ta-lib + stockstats + pandas)."""

from threading import Lock
from typing import Any, cast

import numpy as np
import pandas as pd
from stockstats import StockDataFrame, set_dft_window, wrap
import talib

from stk.errors import IndicatorError
from stk.models.indicator import KlineBar, KlinePeriod, KlineSeries
from stk.services.history import candles_to_df, get_history
from stk.utils.symbol import to_longport_symbol

_EMA_PERIODS = (5, 9, 10, 20, 26, 60)
_KDJ_PERIOD = 9
_WR_PERIOD = 14
_SUPERTREND_PERIOD = 10
_SUPERTREND_MULTIPLIER = 2.5
_stockstats_config_lock = Lock()
_stockstats_configured = False


def _configure_stockstats() -> None:
    """Configure process-wide stockstats defaults once before concurrent scans."""
    global _stockstats_configured
    if _stockstats_configured:
        return
    with _stockstats_config_lock:
        if _stockstats_configured:
            return
        set_dft_window("supertrend", _SUPERTREND_PERIOD)
        _stockstats_configured = True


def _to_stock_frame(df: pd.DataFrame) -> StockDataFrame:
    """Wrap a defensive DataFrame copy with the project's fixed indicator settings."""
    _configure_stockstats()
    stock = cast(StockDataFrame, wrap(df.copy()))
    cast(Any, stock).SUPERTREND_MUL = _SUPERTREND_MULTIPLIER
    return stock


def _stock_values(stock: StockDataFrame, column: str) -> np.ndarray:
    return stock[column].to_numpy(dtype=float)


def _calc_ema(df: pd.DataFrame, params: dict) -> list[dict]:
    periods = params.get("periods", _EMA_PERIODS)
    close = cast(np.ndarray, df["close"])
    emas = {p: talib.EMA(close, timeperiod=p) for p in periods}
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
        cast(np.ndarray, df["close"]), fastperiod=fast, slowperiod=slow, signalperiod=signal
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
    result = talib.RSI(cast(np.ndarray, df["close"]), timeperiod=period)
    return [
        {"date": d, "RSI": None if np.isnan(v) else round(v, 4)}
        for d, v in zip(df["date"], result, strict=False)
    ]


def _calc_kdj_arrays(stock: StockDataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return stockstats KDJ9 using its recursive 2/3 and 1/3 smoothing."""
    return (
        _stock_values(stock, f"kdjk_{_KDJ_PERIOD}"),
        _stock_values(stock, f"kdjd_{_KDJ_PERIOD}"),
        _stock_values(stock, f"kdjj_{_KDJ_PERIOD}"),
    )


def _calc_kdj(stock: StockDataFrame, dates: pd.Series) -> list[dict]:
    k, d, j = _calc_kdj_arrays(stock)
    return [
        {
            "date": date,
            "K": None if np.isnan(kv) else round(kv, 4),
            "D": None if np.isnan(dv) else round(dv, 4),
            "J": None if np.isnan(jv) else round(jv, 4),
        }
        for date, kv, dv, jv in zip(dates, k, d, j, strict=False)
    ]


def _calc_boll(df: pd.DataFrame, params: dict) -> list[dict]:
    period = params.get("timeperiod", 20)
    nbdev = params.get("nbdevup", 2)
    upper, middle, lower = talib.BBANDS(
        cast(np.ndarray, df["close"]), timeperiod=period, nbdevup=nbdev, nbdevdn=nbdev
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


def _calc_atr(
    stock: StockDataFrame,
    dates: pd.Series,
    params: dict,
) -> list[dict]:
    period = params.get("timeperiod", 14)
    result = _stock_values(stock, f"atr_{period}")
    return [
        {"date": d, f"ATR{period}": None if np.isnan(v) else round(v, 4)}
        for d, v in zip(dates, result, strict=False)
    ]


def _calc_wr(stock: StockDataFrame, dates: pd.Series) -> list[dict]:
    """Calculate the 14-period Williams %R oscillator with stockstats."""
    result = _stock_values(stock, f"wr_{_WR_PERIOD}")
    return [
        {"date": date, "WR": None if np.isnan(value) else round(value, 4)}
        for date, value in zip(dates, result, strict=False)
    ]


def _calc_supertrend_arrays(
    stock: StockDataFrame,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return stockstats Supertrend line, direction, and its ATR10 series."""
    supertrend = _stock_values(stock, "supertrend")
    upper = _stock_values(stock, "supertrend_ub")
    lower = _stock_values(stock, "supertrend_lb")
    atr = _stock_values(stock, f"atr_{_SUPERTREND_PERIOD}")

    direction = np.zeros(len(supertrend), dtype=int)
    separated_bands = ~np.isclose(upper, lower)
    direction[np.isclose(supertrend, lower) & separated_bands] = 1
    direction[np.isclose(supertrend, upper) & separated_bands] = -1
    return supertrend, direction, atr


def _calc_supertrend(stock: StockDataFrame, dates: pd.Series) -> list[dict]:
    """Build the stable daily output fields from stockstats Supertrend."""
    supertrend, direction, atr = _calc_supertrend_arrays(stock)

    rows: list[dict] = []
    for d, st, trend, atr_value in zip(dates, supertrend, direction, atr, strict=False):
        trend_name = "bullish" if trend > 0 else "bearish" if trend < 0 else None
        rows.append({
            "date": d,
            "Supertrend": None if np.isnan(st) else round(float(st), 4),
            "SupertrendDirection": trend_name,
            f"ATR{_SUPERTREND_PERIOD}": (
                None if np.isnan(atr_value) else round(float(atr_value), 4)
            ),
        })
    return rows


def _fetch_df(
    symbol: str,
    *,
    period: str = "day",
    count: int = 60,
) -> pd.DataFrame:
    """Fetch history and convert to DataFrame (shared by single/all)."""
    candles = get_history(symbol, period=period, count=count)
    if not candles:
        raise IndicatorError(f"No history data for {symbol}")
    return candles_to_df(candles)


def get_daily(
    symbol: str,
    *,
    period: KlinePeriod = KlinePeriod.DAY,
    count: int = 10,
) -> KlineSeries:
    """Get OHLCV + all indicators merged per day (single history fetch)."""
    warmup = 50
    df = _fetch_df(symbol, period=period, count=count + warmup)
    stock = _to_stock_frame(df)

    # Compute all indicators on full df
    indicator_rows = (
        _calc_ema(df, {}),
        _calc_macd(df, {}),
        _calc_rsi(df, {}),
        _calc_kdj(stock, df["date"]),
        _calc_boll(df, {}),
        _calc_atr(stock, df["date"], {}),
        _calc_wr(stock, df["date"]),
        _calc_supertrend(stock, df["date"]),
    )

    # Take last `count` rows, merge OHLCV + indicators per day
    n = len(df)
    bars: list[KlineBar] = []
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
        for indicator_values in indicator_rows:
            day_data = indicator_values[i]
            for key, value in day_data.items():
                if key != "date":
                    day[key] = value
        bars.append(
            KlineBar(
                date=str(day["date"]),
                open=float(day["open"]),
                high=float(day["high"]),
                low=float(day["low"]),
                close=float(day["close"]),
                volume=int(day["volume"]),
                turnover=_number(day.get("turnover")),
                change_pct=_number(day.get("change_pct")),
                ema5=_number(day.get("EMA5")),
                ema9=_number(day.get("EMA9")),
                ema10=_number(day.get("EMA10")),
                ema20=_number(day.get("EMA20")),
                ema26=_number(day.get("EMA26")),
                ema60=_number(day.get("EMA60")),
                macd=_number(day.get("MACD")),
                macd_signal=_number(day.get("signal")),
                macd_hist=_number(day.get("hist")),
                rsi14=_number(day.get("RSI")),
                kdj_k=_number(day.get("K")),
                kdj_d=_number(day.get("D")),
                kdj_j=_number(day.get("J")),
                wr14=_number(day.get("WR")),
                boll_upper=_number(day.get("upper")),
                boll_middle=_number(day.get("middle")),
                boll_lower=_number(day.get("lower")),
                atr10=_number(day.get("ATR10")),
                atr14=_number(day.get("ATR14")),
                supertrend=_number(day.get("Supertrend")),
                supertrend_direction=day.get("SupertrendDirection"),
            )
        )

    return KlineSeries(symbol=to_longport_symbol(symbol), bars=bars)


def _number(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) else None
