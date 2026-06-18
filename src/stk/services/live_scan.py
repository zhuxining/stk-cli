"""Intraday live scan service."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from loguru import logger
import numpy as np
import pandas as pd
import talib

from stk.errors import IndicatorError
from stk.models.live_scan import (
    LiveFocusItem,
    LiveIgnoredSummary,
    LiveScanResult,
    LiveScanSummary,
    LiveSignal,
    LiveStrength,
)
from stk.models.quote import Quote
from stk.models.scan import MonitorUniverse, ScanError
from stk.models.score import DecisionSignal, ScoreResult, SignalStatus, SignalStrength
from stk.services.history import candles_to_df, get_uncached_history
from stk.services.quote import get_realtime_quotes
from stk.services.score import calc_score
from stk.services.watchlist import get_watchlist
from stk.utils.symbol import to_longport_symbol
from stk.utils.trading_session import daily_bar_date, market_daily_cutoff

_LOCAL_TZ = ZoneInfo("Asia/Shanghai")
_ENTRY_SIGNALS: set[DecisionSignal] = {"趋势买入", "超卖修复"}
_EXIT_SIGNALS: set[DecisionSignal] = {"趋势退出"}
_ACTIVE_STATUSES: set[SignalStatus] = {"new", "active"}
_ACTIVE_STRENGTHS: set[SignalStrength | None] = {"推荐", "预警"}
_SUPPORTED_TIMEFRAMES = {"5m": 5, "15m": 15}
_DEFAULT_BAR_COUNT = 80
_MIN_INTRADAY_BARS = 30
_VOLUME_STRONG_RATIO = 1.5
_OVERHEAT_RSI = 75
_STRONG_OVERHEAT_RSI = 80
_OVERHEAT_VWAP_DEVIATION = 3.5
_STRONG_OVERHEAT_VWAP_DEVIATION = 5.0


@dataclass(frozen=True)
class _LiveMetrics:
    close: float
    prev_close: float | None
    ema20: float | None
    prev_ema20: float | None
    vwap: float | None
    prev_vwap: float | None
    rsi14: float | None
    volume_ratio: float | None
    open_range_low: float | None
    open_range_high: float | None


@dataclass(frozen=True)
class _LiveDecision:
    signal: LiveSignal
    strength: LiveStrength
    trigger: str
    risk_line: float | None


def _timeframe_minutes(timeframe: str) -> int:
    minutes = _SUPPORTED_TIMEFRAMES.get(timeframe)
    if minutes is None:
        allowed = "/".join(_SUPPORTED_TIMEFRAMES)
        raise IndicatorError(f"Unsupported live timeframe: {timeframe}. Use {allowed}")
    return minutes


def _bar_datetime(value: object, symbol: str) -> pd.Timestamp | None:
    tz, _ = market_daily_cutoff(symbol)
    timestamp = pd.to_datetime(str(value), errors="coerce")
    if pd.isna(timestamp):
        return None
    if timestamp.tzinfo is not None:
        return timestamp.tz_convert(tz)
    return timestamp.tz_localize(tz)


def _closed_intraday_df(
    df: pd.DataFrame,
    symbol: str,
    *,
    timeframe: str,
    now: datetime | None = None,
) -> pd.DataFrame:
    if df.empty:
        return df

    minutes = _timeframe_minutes(timeframe)
    tz, _ = market_daily_cutoff(symbol)
    current = now or datetime.now(tz)
    current = current.astimezone(tz) if current.tzinfo else current.replace(tzinfo=tz)
    last_start = _bar_datetime(df.iloc[-1]["date"], symbol)
    if last_start is not None and current < last_start.to_pydatetime() + timedelta(minutes=minutes):
        return df.iloc[:-1].copy()
    return df


def _safe_last(values: np.ndarray) -> float | None:
    value = values[-1]
    return None if np.isnan(value) else round(float(value), 4)


def _safe_prev(values: np.ndarray) -> float | None:
    if len(values) < 2:
        return None
    value = values[-2]
    return None if np.isnan(value) else round(float(value), 4)


def _round(value: float | None, digits: int = 4) -> float | None:
    return None if value is None or np.isnan(value) else round(float(value), digits)


def _metric_series(df: pd.DataFrame) -> pd.Series:
    if "turnover" in df.columns and df["turnover"].fillna(0).sum() > 0:
        return df["turnover"].astype(float)
    return df["volume"].astype(float)


def _vwap(df: pd.DataFrame) -> float | None:
    if df.empty:
        return None
    volume = df["volume"].astype(float)
    total_volume = float(volume.sum())
    if total_volume <= 0:
        return None
    turnover = df.get("turnover")
    if turnover is not None and turnover.fillna(0).sum() > 0:
        return round(float(turnover.astype(float).sum()) / total_volume, 4)
    close = df["close"].astype(float)
    return round(float((close * volume).sum()) / total_volume, 4)


def _latest_session_df(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    tz, _ = market_daily_cutoff(symbol)
    dates = df["date"].map(lambda value: daily_bar_date(value, tz))
    latest_date = dates.iloc[-1]
    return df.loc[dates == latest_date].copy()


def _volume_ratio(df: pd.DataFrame) -> float | None:
    if len(df) < 6:
        return None
    values = _metric_series(df)
    current = float(values.iloc[-1])
    previous = values.iloc[max(0, len(values) - 21) : -1]
    average = float(previous.mean()) if not previous.empty else 0
    if average <= 0:
        return None
    return round(current / average, 2)


def _open_range(session_df: pd.DataFrame, timeframe: str) -> tuple[float | None, float | None]:
    if session_df.empty:
        return None, None
    bars = max(1, 30 // _timeframe_minutes(timeframe))
    window = session_df.head(bars)
    return round(float(window["low"].min()), 4), round(float(window["high"].max()), 4)


def _build_metrics(df: pd.DataFrame, symbol: str, timeframe: str) -> _LiveMetrics:
    close = df["close"].to_numpy(dtype=float)
    ema20 = talib.EMA(close, timeperiod=20)
    rsi = talib.RSI(close, timeperiod=14)
    session_df = _latest_session_df(df, symbol)
    open_low, open_high = _open_range(session_df, timeframe)

    return _LiveMetrics(
        close=round(float(close[-1]), 4),
        prev_close=round(float(close[-2]), 4) if len(close) >= 2 else None,
        ema20=_safe_last(ema20),
        prev_ema20=_safe_prev(ema20),
        vwap=_vwap(session_df),
        prev_vwap=_vwap(session_df.iloc[:-1]) if len(session_df) >= 2 else None,
        rsi14=_safe_last(rsi),
        volume_ratio=_volume_ratio(df),
        open_range_low=open_low,
        open_range_high=open_high,
    )


def _valid_values(*values: float | None) -> list[float]:
    return [value for value in values if value is not None]


def _crossed_up(metrics: _LiveMetrics) -> bool:
    if metrics.prev_close is None:
        return False
    crossed_ema = metrics.prev_ema20 is not None and metrics.prev_close <= metrics.prev_ema20
    crossed_vwap = metrics.prev_vwap is not None and metrics.prev_close <= metrics.prev_vwap
    return crossed_ema or crossed_vwap


def _crossed_down(metrics: _LiveMetrics) -> bool:
    if metrics.prev_close is None:
        return False
    crossed_ema = metrics.prev_ema20 is not None and metrics.prev_close >= metrics.prev_ema20
    crossed_vwap = metrics.prev_vwap is not None and metrics.prev_close >= metrics.prev_vwap
    return crossed_ema or crossed_vwap


def _above_intraday_trend(metrics: _LiveMetrics) -> bool:
    values = _valid_values(metrics.ema20, metrics.vwap)
    return bool(values) and all(metrics.close > value for value in values)


def _below_intraday_trend(metrics: _LiveMetrics) -> bool:
    values = _valid_values(metrics.ema20, metrics.vwap)
    below_trend = bool(values) and all(metrics.close < value for value in values)
    below_open_range = metrics.open_range_low is not None and metrics.close < metrics.open_range_low
    return below_trend or below_open_range


def _vwap_deviation(metrics: _LiveMetrics) -> float | None:
    if metrics.vwap is None or metrics.vwap <= 0:
        return None
    return round((metrics.close - metrics.vwap) / metrics.vwap * 100, 2)


def _is_overheated(metrics: _LiveMetrics) -> bool:
    deviation = _vwap_deviation(metrics)
    return (metrics.rsi14 is not None and metrics.rsi14 >= _OVERHEAT_RSI) or (
        deviation is not None and deviation >= _OVERHEAT_VWAP_DEVIATION
    )


def _is_strong_overheat(metrics: _LiveMetrics) -> bool:
    deviation = _vwap_deviation(metrics)
    return (metrics.rsi14 is not None and metrics.rsi14 >= _STRONG_OVERHEAT_RSI) or (
        deviation is not None and deviation >= _STRONG_OVERHEAT_VWAP_DEVIATION
    )


def _has_strong_volume(metrics: _LiveMetrics) -> bool:
    return metrics.volume_ratio is not None and metrics.volume_ratio >= _VOLUME_STRONG_RATIO


def _strength(
    metrics: _LiveMetrics,
    *,
    crossed: bool,
    overheated: bool = False,
) -> LiveStrength:
    if overheated:
        return "强提醒" if _is_strong_overheat(metrics) else "普通提醒"
    if crossed and _has_strong_volume(metrics):
        return "强提醒"
    return "普通提醒"


def _risk_line(signal: LiveSignal, metrics: _LiveMetrics) -> float | None:
    if signal == "实时跟随":
        return _round(max(_valid_values(metrics.ema20, metrics.vwap), default=np.nan))
    if signal == "实时转弱":
        return _round(
            max(_valid_values(metrics.ema20, metrics.vwap, metrics.open_range_low), default=np.nan)
        )
    if signal == "实时过热":
        return _round(metrics.vwap or metrics.ema20)
    return None


def _classify_live(score: ScoreResult, metrics: _LiveMetrics) -> _LiveDecision:
    daily_signal = score.decision.signal

    if daily_signal in _ENTRY_SIGNALS and _below_intraday_trend(metrics):
        signal: LiveSignal = "实时转弱"
        return _LiveDecision(
            signal=signal,
            strength=_strength(metrics, crossed=_crossed_down(metrics)),
            trigger="日线偏多，但分钟线跌破 VWAP/EMA20 或开盘区间低点",
            risk_line=_risk_line(signal, metrics),
        )

    if daily_signal in _ENTRY_SIGNALS and _is_overheated(metrics):
        signal = "实时过热"
        return _LiveDecision(
            signal=signal,
            strength=_strength(metrics, crossed=False, overheated=True),
            trigger="日线偏多，但分钟 RSI 或 VWAP 偏离过热",
            risk_line=_risk_line(signal, metrics),
        )

    if daily_signal in _ENTRY_SIGNALS and _above_intraday_trend(metrics):
        signal = "实时跟随"
        return _LiveDecision(
            signal=signal,
            strength=_strength(metrics, crossed=_crossed_up(metrics)),
            trigger="日线偏多，分钟收盘站上 VWAP 和 EMA20",
            risk_line=_risk_line(signal, metrics),
        )

    if daily_signal in _EXIT_SIGNALS and _below_intraday_trend(metrics):
        signal = "实时转弱"
        return _LiveDecision(
            signal=signal,
            strength=_strength(metrics, crossed=_crossed_down(metrics)),
            trigger="日线退出信号下，分钟线继续弱于 VWAP/EMA20",
            risk_line=_risk_line(signal, metrics),
        )

    return _LiveDecision(
        signal="实时观察",
        strength="观察",
        trigger="日线背景存在，但分钟线未形成收线触发",
        risk_line=None,
    )


def _is_daily_candidate(score: ScoreResult) -> bool:
    decision = score.decision
    return (
        decision.signal in (_ENTRY_SIGNALS | _EXIT_SIGNALS)
        and decision.strength in _ACTIVE_STRENGTHS
        and decision.signal_status in _ACTIVE_STATUSES
    )


def _scan_one_symbol(
    symbol: str,
    *,
    quote: Quote | None,
    name: str,
    timeframe: str,
    count: int,
) -> LiveFocusItem | None:
    score = calc_score(symbol)
    if not _is_daily_candidate(score):
        return None

    candles = get_uncached_history(symbol, period=timeframe, count=count)
    if not candles:
        raise IndicatorError(f"No intraday history for {symbol}")

    df = _closed_intraday_df(candles_to_df(candles), symbol, timeframe=timeframe)
    if len(df) < _MIN_INTRADAY_BARS:
        raise IndicatorError(
            f"Insufficient intraday history for {symbol} "
            f"(need>={_MIN_INTRADAY_BARS}, got {len(df)})"
        )

    metrics = _build_metrics(df, symbol, timeframe)
    decision = _classify_live(score, metrics)
    if decision.signal == "实时观察":
        return None

    return LiveFocusItem(
        symbol=to_longport_symbol(symbol),
        name=name,
        daily_signal=score.decision.signal,
        daily_strength=score.decision.strength,
        live_signal=decision.signal,
        strength=decision.strength,
        trigger=decision.trigger,
        last=quote.last if quote else Decimal(str(metrics.close)),
        change_pct=quote.change_pct if quote else None,
        risk_line=decision.risk_line,
        volume_ratio=metrics.volume_ratio,
        vwap=metrics.vwap,
        ema20=metrics.ema20,
        rsi14=metrics.rsi14,
    )


def _quote_map(symbols: list[str], names: dict[str, str]) -> dict[str, Quote]:
    try:
        quotes = get_realtime_quotes(symbols)
    except Exception as err:
        logger.debug(f"Live scan quote fetch failed: {err}")
        return {}

    result = {quote.symbol: quote for quote in quotes}
    for quote in quotes:
        if quote.name:
            names.setdefault(quote.symbol, quote.name)
    return result


def _as_of() -> str:
    return datetime.now(_LOCAL_TZ).isoformat(timespec="seconds")


def _summary(focus: list[LiveFocusItem], observed: int) -> LiveScanSummary:
    return LiveScanSummary(
        focus_count=len(focus),
        follow_count=sum(item.live_signal == "实时跟随" for item in focus),
        weaken_count=sum(item.live_signal == "实时转弱" for item in focus),
        overheated_count=sum(item.live_signal == "实时过热" for item in focus),
        observe_count=observed,
    )


def _sort_key(item: LiveFocusItem) -> tuple[int, int]:
    signal_rank = {"实时转弱": 0, "实时跟随": 1, "实时过热": 2, "实时观察": 3}
    strength_rank = {"强提醒": 0, "普通提醒": 1, "观察": 2}
    return signal_rank[item.live_signal], strength_rank[item.strength]


def live_summary(
    symbols: list[str],
    *,
    names: dict[str, str] | None = None,
    universe_name: str = "ad-hoc",
    timeframe: str = "15m",
    count: int = _DEFAULT_BAR_COUNT,
    max_workers: int = 8,
) -> LiveScanResult:
    """Run intraday scan over symbols."""
    _timeframe_minutes(timeframe)
    symbol_names = names or {}
    lp_symbols = [to_longport_symbol(symbol) for symbol in symbols]
    quotes = _quote_map(lp_symbols, symbol_names)
    focus: list[LiveFocusItem] = []
    errors: list[ScanError] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _scan_one_symbol,
                symbol,
                quote=quotes.get(symbol),
                name=symbol_names.get(symbol, symbol_names.get(to_longport_symbol(symbol), "")),
                timeframe=timeframe,
                count=count,
            ): symbol
            for symbol in lp_symbols
        }
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                if item := future.result():
                    focus.append(item)
            except Exception as err:
                logger.debug(f"Live scan failed for {symbol}: {err}")
                errors.append(ScanError(symbol=to_longport_symbol(symbol), reason=str(err)))

    focus.sort(key=_sort_key)
    scanned = len(symbols) - len(errors)
    observed = max(scanned - len(focus), 0)
    return LiveScanResult(
        as_of=_as_of(),
        timeframe=timeframe,
        universe=MonitorUniverse(
            name=universe_name,
            total=len(symbols),
            scanned=scanned,
            failed=len(errors),
        ),
        summary=_summary(focus, observed),
        focus=focus,
        ignored=LiveIgnoredSummary(no_live_signal_count=observed),
        errors=errors,
    )


def scan_live_watchlist(
    name: str,
    *,
    timeframe: str = "15m",
    count: int = _DEFAULT_BAR_COUNT,
) -> LiveScanResult:
    """Run intraday scan over a watchlist group."""
    watchlist = get_watchlist(name)
    symbols = [security.symbol for security in watchlist.securities]
    names = {security.symbol: security.name for security in watchlist.securities}
    return live_summary(
        symbols,
        names=names,
        universe_name=name,
        timeframe=timeframe,
        count=count,
    )
