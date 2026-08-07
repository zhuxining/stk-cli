"""Absolute-state ETF rotation analysis and Longport snapshot routing."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import math
from typing import Final, cast

from longport.openapi import SecuritiesUpdateMode
import numpy as np
import pandas as pd
from stockstats import StockDataFrame, set_dft_window, wrap
import talib

from stk.errors import IndicatorError, SourceError, StkError, error_code
from stk.models.rotation import (
    FadeSeverity,
    RotationAction,
    RotationFactors,
    RotationFailure,
    RotationIndicators,
    RotationItem,
    RotationPoolSummary,
    RotationResult,
    RotationRouteResult,
    RotationRouteTarget,
    RotationSetup,
    RotationSignal,
    RotationStage,
    RotationState,
    RotationSummary,
    RotationTrend,
)
from stk.services.history import candles_to_df, get_history
from stk.services.watchlist import add_symbols, get_watchlist
from stk.utils.symbol import to_longport_symbol
from stk.utils.trading_session import is_unclosed_daily_bar

_MIN_BARS: Final = 70
_HISTORY_BARS: Final = 90
_MIN_POOL_SIZE: Final = 5
_EMERGING_WINDOW: Final = 2
_FADING_WINDOW: Final = 3
_ACTIVE_LOOKBACK: Final = 10
# ETF 轮动模型参数：Supertrend(10, 3)。注意股票信号模型（services/indicator.py）
# 有意使用 Supertrend(10, 2.5)，两者是不同模型；共享实现时须显式传参，
# 不要统一这里的常量。
_SUPERTREND_PERIOD: Final = 10
_SUPERTREND_MULTIPLIER: Final = 3
set_dft_window("supertrend", _SUPERTREND_PERIOD)
_TURNOVER_RATIO_LONG: Final = 20
_TURNOVER_RATIO_SHORT: Final = 5
_REBOUND_EMA20_GAP_ATR: Final = 0.25
_REBOUND_SLOPE_FLOOR: Final = -0.01


@dataclass(slots=True)
class _Series:
    symbol: str
    name: str
    frame: pd.DataFrame


@dataclass(slots=True)
class _Point:
    series: _Series
    index: int
    metrics: dict[str, float]
    close: np.ndarray
    ema9: np.ndarray
    ema26: np.ndarray
    supertrend_direction: np.ndarray


@dataclass(slots=True, frozen=True)
class _Classification:
    state: RotationState
    setup: RotationSetup | None = None
    severity: FadeSeverity | None = None


def _finite(value: float, label: str) -> float:
    if not math.isfinite(value):
        raise IndicatorError(f"Indicator unavailable: {label}")
    return float(value)


def _load_series(symbol: str, name: str) -> _Series:
    candles = get_history(symbol, period="day", count=_HISTORY_BARS)
    frame = candles_to_df(candles).sort_values("date").reset_index(drop=True)
    if not frame.empty and is_unclosed_daily_bar(frame.iloc[-1]["date"], symbol):
        frame = frame.iloc[:-1].copy()
    if len(frame) < _MIN_BARS:
        raise SourceError(f"At least {_MIN_BARS} confirmed daily bars required")
    return _Series(symbol=to_longport_symbol(symbol), name=name, frame=frame)


def _consecutive_count(close: np.ndarray, index: int, *, up: bool) -> int:
    """Count consecutive confirmed bars closing higher/lower than the prior bar."""
    count = 0
    for i in range(index, 0, -1):
        if (close[i] > close[i - 1]) == up:
            count += 1
        else:
            break
    return count


def _indicator_points(series: _Series, indices: range) -> dict[int, _Point]:
    frame = series.frame
    close = frame["close"].to_numpy(dtype=float)
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)
    volume = frame["volume"].to_numpy(dtype=float)
    log_close = np.log(close)
    log_return = np.empty(len(close), dtype=float)
    log_return[0] = np.nan
    log_return[1:] = np.diff(log_close)
    time_index = np.arange(len(close), dtype=float)

    stock = cast(StockDataFrame, wrap(frame.copy()))
    stock.SUPERTREND_MUL = _SUPERTREND_MULTIPLIER
    supertrend = stock["supertrend"].to_numpy(dtype=float)
    upper = stock["supertrend_ub"].to_numpy(dtype=float)
    lower = stock["supertrend_lb"].to_numpy(dtype=float)
    atr10 = stock[f"atr_{_SUPERTREND_PERIOD}"].to_numpy(dtype=float)
    separated = ~np.isclose(upper, lower)
    direction = np.zeros(len(supertrend), dtype=int)
    direction[np.isclose(supertrend, lower) & separated] = 1
    direction[np.isclose(supertrend, upper) & separated] = -1

    macd, macd_signal, macd_hist = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
    arrays = {
        "return5": talib.ROCP(close, timeperiod=5),
        "return20": talib.ROCP(close, timeperiod=20),
        "return60": talib.ROCP(close, timeperiod=60),
        "vol20": talib.STDDEV(log_return, timeperiod=20) * math.sqrt(20),
        "vol60": talib.STDDEV(log_return, timeperiod=60) * math.sqrt(60),
        "slope20": talib.LINEARREG_SLOPE(log_close, timeperiod=20),
        "correlation20": talib.CORREL(log_close, time_index, timeperiod=20),
        "ema5": talib.EMA(close, timeperiod=5),
        "ema9": talib.EMA(close, timeperiod=9),
        "ema10": talib.EMA(close, timeperiod=10),
        "ema20": talib.EMA(close, timeperiod=20),
        "ema26": talib.EMA(close, timeperiod=26),
        "ema60": talib.EMA(close, timeperiod=60),
        "rsi14": talib.RSI(close, timeperiod=14),
        "adx14": talib.ADX(high, low, close, timeperiod=14),
        "mfi14": talib.MFI(high, low, close, volume, timeperiod=14),
        "macd": macd,
        "macd_signal": macd_signal,
        "macd_hist": macd_hist,
    }
    turnover = frame["turnover"].to_numpy(dtype=float)
    points: dict[int, _Point] = {}
    for index in indices:
        values = {key: _finite(array[index], key) for key, array in arrays.items()}
        values["previous_return5"] = _finite(arrays["return5"][index - 5], "previous_return5")
        values["close"] = float(close[index])
        values["atr10"] = _finite(atr10[index], "atr10")
        values["supertrend"] = _finite(supertrend[index], "supertrend")
        values["ema20_slope5"] = values["ema20"] / arrays["ema20"][index - 5] - 1
        values["entry_distance_atr"] = (values["close"] - values["ema20"]) / values["atr10"]
        previous_turnover_window = turnover[
            index - _TURNOVER_RATIO_LONG - _TURNOVER_RATIO_SHORT + 1 : index
            - _TURNOVER_RATIO_SHORT
            + 1
        ]
        current_turnover_window = turnover[index - _TURNOVER_RATIO_SHORT + 1 : index + 1]
        previous_turnover = float(np.mean(previous_turnover_window))
        values["turnover_ratio"] = (
            float(np.mean(current_turnover_window)) / previous_turnover
            if previous_turnover > 0
            else 1.0
        )
        values["consecutive_up"] = _consecutive_count(close, index, up=True)
        values["consecutive_down"] = _consecutive_count(close, index, up=False)
        points[index] = _Point(
            series=series,
            index=index,
            metrics=values,
            close=close,
            ema9=arrays["ema9"],
            ema26=arrays["ema26"],
            supertrend_direction=direction,
        )
    return points


def percentile(values: pd.Series) -> pd.Series:
    """Return percentiles with ties sharing their average rank."""
    valid = values.dropna()
    if len(valid) <= 1:
        return pd.Series(50.0, index=values.index)
    result = (values.rank(method="average") - 1) / (len(valid) - 1) * 100
    return result.fillna(50.0)


def _cross_age(left: np.ndarray, right: np.ndarray, index: int, *, bullish: bool) -> int | None:
    for age in range(_FADING_WINDOW):
        current = index - age
        previous = current - 1
        if np.isnan([left[previous], right[previous], left[current], right[current]]).any():
            continue
        crossed = (
            left[previous] <= right[previous] and left[current] > right[current]
            if bullish
            else left[previous] >= right[previous] and left[current] < right[current]
        )
        if crossed:
            return age
    return None


def _direction_age(direction: np.ndarray, index: int, *, bullish: bool) -> int | None:
    target = 1 if bullish else -1
    for age in range(_FADING_WINDOW):
        current = index - age
        if direction[current - 1] == -target and direction[current] == target:
            return age
    return None


def _events(point: _Point) -> RotationSignal:
    values = point.metrics
    index = point.index
    direction = point.supertrend_direction
    st_bull_age = _direction_age(direction, index, bullish=True)
    st_bear_age = _direction_age(direction, index, bullish=False)
    golden_age = _cross_age(point.ema9, point.ema26, index, bullish=True)
    death_age = _cross_age(point.ema9, point.ema26, index, bullish=False)
    entry = values["rsi14"] < 75 and values["close"] <= values["ema20"] + 2 * values["atr10"]
    return RotationSignal(
        supertrend_bullish_event=(st_bull_age is not None and st_bull_age < _EMERGING_WINDOW),
        supertrend_bearish_event=st_bear_age is not None,
        ema_golden_cross=golden_age is not None and golden_age < _EMERGING_WINDOW,
        ema_death_cross=death_age is not None,
        supertrend_bullish_age=st_bull_age,
        supertrend_bearish_age=st_bear_age,
        ema_golden_cross_age=golden_age,
        ema_death_cross_age=death_age,
        entry_eligible=entry,
    )


def _confirmed_emerging(point: _Point, signal: RotationSignal) -> bool:
    values = point.metrics
    return (
        signal.supertrend_bullish_event
        and point.supertrend_direction[point.index] > 0
        and values["close"] > values["ema20"]
        and values["return5"] > 0
    )


def _rebound_emerging(point: _Point) -> bool:
    values = point.metrics
    return (
        values["return5"] > 0
        and values["return5"] > values["previous_return5"]
        and values["close"] > values["ema9"]
        and values["close"] >= values["ema20"] - _REBOUND_EMA20_GAP_ATR * values["atr10"]
        and values["ema20_slope5"] > _REBOUND_SLOPE_FLOOR
    )


def _strong(point: _Point) -> bool:
    values = point.metrics
    return (
        point.supertrend_direction[point.index] > 0
        and values["close"] > values["ema20"]
        and values["ema20_slope5"] > 0
        and values["return20"] > 0
        and values["consecutive_down"] < 3
    )


def _was_confirmed_active(history: list[_Point]) -> bool:
    for point in history[-_ACTIVE_LOOKBACK:]:
        signal = _events(point)
        if _confirmed_emerging(point, signal) or _strong(point):
            return True
    return False


def _fade_severity(point: _Point, history: list[_Point]) -> FadeSeverity | None:
    if not _was_confirmed_active(history):
        return None
    values = point.metrics
    signal = _events(point)
    current_st_bearish = point.supertrend_direction[point.index] < 0
    severe = (
        current_st_bearish
        and values["close"] < values["ema20"]
        and values["macd_hist"] < 0
        and values["adx14"] > history[-2].metrics["adx14"]
    )
    if severe:
        return "severe"
    two_closes_below = (
        len(history) >= 1
        and history[-1].metrics["close"] < history[-1].metrics["ema20"]
        and values["close"] < values["ema20"]
    )
    confirmed = (
        (signal.supertrend_bearish_event and current_st_bearish)
        or (values["consecutive_down"] >= 3 and values["close"] < values["ema20"])
        or (two_closes_below and values["ema20_slope5"] <= 0)
    )
    if confirmed:
        return "confirmed"
    mild = (
        values["return5"] < 0
        and values["ema5"] < values["ema10"]
        and values["macd_hist"] < 0
        and values["close"] <= values["ema20"] + 0.5 * values["atr10"]
    )
    return "mild" if mild else None


def classify_state(point: _Point, history: list[_Point]) -> _Classification:
    """Classify one point using absolute structure and causal history."""
    if severity := _fade_severity(point, history):
        return _Classification(state="fading", severity=severity)
    signal = _events(point)
    if _confirmed_emerging(point, signal):
        return _Classification(state="emerging", setup="confirmed")
    if _strong(point):
        return _Classification(state="strong")
    if _rebound_emerging(point):
        return _Classification(state="emerging", setup="rebound")
    return _Classification(state="inactive")


def determine_action(
    stage: RotationStage,
    *,
    setup: RotationSetup | None,
    severity: FadeSeverity | None,
    entry_eligible: bool,
) -> RotationAction:
    """Map a v2 stage and its qualifier to one action."""
    if stage == "fading":
        return "reduce" if severity == "mild" else "exit"
    if stage == "strong":
        return "hold"
    return "rotate_in" if setup == "confirmed" and entry_eligible else "watch"


def _rank_scores(
    table: pd.DataFrame,
    classifications: dict[str, _Classification],
) -> pd.Series:
    scores = pd.Series(0.0, index=table.index)
    for stage in ("emerging", "strong", "fading"):
        symbols = [symbol for symbol, item in classifications.items() if item.state == stage]
        if not symbols:
            continue
        subset = table.loc[symbols]
        if stage == "emerging":
            scores.loc[symbols] = (
                percentile(subset["acceleration_abs"]) * 0.40
                + percentile(subset["quality"]) * 0.20
                + percentile(subset["turnover_confirmation"]) * 0.20
                + percentile(-subset["entry_distance_atr"].abs()) * 0.20
            )
        elif stage == "strong":
            scores.loc[symbols] = (
                percentile(subset["absolute_rm20"]) * 0.30
                + percentile(subset["quality"]) * 0.25
                + percentile(subset["adx14"]) * 0.20
                + percentile(subset["macd_health"]) * 0.15
                + percentile(subset["volume_confirmation"]) * 0.10
            )
        else:
            scores.loc[symbols] = (
                percentile(subset["downside_return5"]) * 0.35
                + percentile(subset["ema20_break_atr"]) * 0.30
                + percentile(subset["bearish_macd"]) * 0.20
                + percentile(subset["downside_turnover"]) * 0.15
            )
    return scores


def _cross_section(
    pool: str,
    current: list[_Point],
    histories: dict[str, list[_Point]],
) -> tuple[list[RotationItem], int]:
    table = pd.DataFrame(
        [point.metrics for point in current], index=[point.series.symbol for point in current]
    )
    vol20_floor = float(table["vol20"].quantile(0.1))
    vol60_floor = float(table["vol60"].quantile(0.1))
    adjusted20 = table["vol20"].clip(lower=max(vol20_floor, np.finfo(float).eps))
    adjusted60 = table["vol60"].clip(lower=max(vol60_floor, np.finfo(float).eps))
    excess5 = table["return5"] - table["return5"].median()
    previous_excess5 = table["previous_return5"] - table["previous_return5"].median()
    table["rm20"] = (table["return20"] - table["return20"].median()) / adjusted20
    table["rm60"] = (table["return60"] - table["return60"].median()) / adjusted60
    table["absolute_rm20"] = table["return20"] / adjusted20
    table["quality"] = table["slope20"] * table["correlation20"].pow(2) / adjusted20
    table["acceleration"] = (excess5 - previous_excess5) / adjusted20
    table["acceleration_abs"] = (table["return5"] - table["previous_return5"]) / adjusted20
    table["turnover_confirmation"] = np.sign(excess5) * np.log(
        table["turnover_ratio"].clip(lower=np.finfo(float).eps)
    )
    table["mfi_confirmation"] = (table["mfi14"] - 50) / 50
    table["volume_confirmation"] = (
        percentile(table["turnover_confirmation"]) * 0.70
        + percentile(table["mfi_confirmation"]) * 0.30
    )
    atr_fraction = table["atr10"] / table["close"]
    table["macd_health"] = table["macd_hist"] / table["atr10"]
    table["downside_return5"] = -table["return5"] / atr_fraction
    table["ema20_break_atr"] = (table["ema20"] - table["close"]) / table["atr10"]
    table["bearish_macd"] = -table["macd_hist"] / table["atr10"]
    table["downside_turnover"] = np.log(table["turnover_ratio"].clip(lower=np.finfo(float).eps))

    classifications = {
        point.series.symbol: classify_state(point, histories[point.series.symbol])
        for point in current
    }
    scores = _rank_scores(table, classifications)
    mean_turnovers = pd.Series({
        point.series.symbol: float(
            point.series.frame.iloc[: point.index + 1]["turnover"].tail(_TURNOVER_RATIO_LONG).mean()
        )
        for point in current
    })
    liquidity_cutoff = float(mean_turnovers.quantile(0.2))

    items: list[RotationItem] = []
    for point in current:
        symbol = point.series.symbol
        classification = classifications[symbol]
        if classification.state == "inactive":
            continue
        stage = classification.state
        values = point.metrics
        history = histories[symbol]
        previous = history[-1]
        previous_state = classify_state(previous, history[:-1]).state
        signal = _events(point)
        current_st = point.supertrend_direction[point.index] > 0
        if current_st and values["close"] > values["ema20"] and values["ema20_slope5"] > 0:
            trend: RotationTrend = "bullish"
        elif not current_st and values["close"] < values["ema20"] and values["ema20_slope5"] < 0:
            trend = "bearish"
        else:
            trend = "neutral"
        warnings: list[str] = []
        if mean_turnovers[symbol] <= liquidity_cutoff:
            warnings.append("low_liquidity")
        if values["rsi14"] >= 75:
            warnings.append("overheated")
        if values["close"] > values["ema20"] + 2 * values["atr10"]:
            warnings.append("overextended")
        items.append(
            RotationItem(
                pool=pool,
                symbol=symbol,
                name=point.series.name,
                as_of=str(point.series.frame.iloc[point.index]["date"]),
                stage=stage,
                previous_state=previous_state,
                stage_changed=previous_state != stage,
                action=determine_action(
                    stage,
                    setup=classification.setup,
                    severity=classification.severity,
                    entry_eligible=signal.entry_eligible,
                ),
                trend=trend,
                rank_score=round(float(scores[symbol]), 4),
                setup=classification.setup,
                fade_severity=classification.severity,
                factors=RotationFactors(
                    return5=values["return5"],
                    previous_return5=values["previous_return5"],
                    return20=values["return20"],
                    return60=values["return60"],
                    pool_median_return5=float(table["return5"].median()),
                    pool_median_return20=float(table["return20"].median()),
                    pool_median_return60=float(table["return60"].median()),
                    vol20=values["vol20"],
                    vol60=values["vol60"],
                    adjusted_vol20=float(adjusted20[symbol]),
                    adjusted_vol60=float(adjusted60[symbol]),
                    current_excess5=float(excess5[symbol]),
                    previous_excess5=float(previous_excess5[symbol]),
                    relative_momentum20=float(table.loc[symbol, "rm20"]),
                    relative_momentum60=float(table.loc[symbol, "rm60"]),
                    trend_quality=float(table.loc[symbol, "quality"]),
                    acceleration=float(table.loc[symbol, "acceleration"]),
                    ema20_slope5=values["ema20_slope5"],
                    entry_distance_atr=values["entry_distance_atr"],
                    turnover_ratio=values["turnover_ratio"],
                    turnover_confirmation=float(table.loc[symbol, "turnover_confirmation"]),
                    mfi_confirmation=float(table.loc[symbol, "mfi_confirmation"]),
                    volume_confirmation=float(table.loc[symbol, "volume_confirmation"]),
                ),
                indicators=RotationIndicators(
                    close=values["close"],
                    ema5=values["ema5"],
                    ema9=values["ema9"],
                    ema10=values["ema10"],
                    ema20=values["ema20"],
                    ema26=values["ema26"],
                    ema60=values["ema60"],
                    rsi14=values["rsi14"],
                    adx14=values["adx14"],
                    mfi14=values["mfi14"],
                    macd=values["macd"],
                    macd_signal=values["macd_signal"],
                    macd_hist=values["macd_hist"],
                    atr10=values["atr10"],
                    atr_pct=values["atr10"] / values["close"] * 100,
                    supertrend=values["supertrend"],
                    supertrend_bullish=current_st,
                    consecutive_up=values["consecutive_up"],
                    consecutive_down=values["consecutive_down"],
                ),
                signal=signal,
                warnings=warnings,
            )
        )
    inactive = sum(item.state == "inactive" for item in classifications.values())
    return items, inactive


def _analyze_pool(
    pool: str,
    symbols: list[tuple[str, str]],
) -> tuple[list[RotationItem], RotationPoolSummary, list[RotationFailure]]:
    series: list[_Series] = []
    failures: list[RotationFailure] = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(_load_series, symbol, name): symbol for symbol, name in symbols}
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                series.append(future.result())
            except Exception as err:
                failures.append(
                    RotationFailure(
                        pool=pool,
                        symbol=to_longport_symbol(symbol),
                        code=error_code(err),
                        message=str(err),
                    )
                )
    if not series:
        raise SourceError(f"Rotation pool '{pool}' has no analyzable symbols")
    latest_dates = [str(item.frame.iloc[-1]["date"]) for item in series]
    date_counts = Counter(latest_dates)
    largest_count = max(date_counts.values())
    as_of = max(date for date, count in date_counts.items() if count == largest_count)
    aligned: list[_Series] = []
    for item in series:
        if str(item.frame.iloc[-1]["date"]) != as_of:
            failures.append(
                RotationFailure(
                    pool=pool,
                    symbol=item.symbol,
                    code="date_mismatch",
                    message=f"Latest confirmed bar does not match pool as_of {as_of}",
                )
            )
        else:
            aligned.append(item)
    if len(aligned) < _MIN_POOL_SIZE:
        raise SourceError(
            f"Rotation pool '{pool}' requires at least {_MIN_POOL_SIZE} successful symbols"
        )

    current: list[_Point] = []
    histories: dict[str, list[_Point]] = {}
    for item in aligned:
        try:
            end = len(item.frame) - 1
            start = end - _ACTIVE_LOOKBACK - _FADING_WINDOW
            point_map = _indicator_points(item, range(start, end + 1))
            current.append(point_map[end])
            histories[item.symbol] = [point_map[index] for index in range(start, end)]
        except Exception as err:
            failures.append(
                RotationFailure(
                    pool=pool,
                    symbol=item.symbol,
                    code=error_code(err),
                    message=str(err),
                )
            )
    if len(current) < _MIN_POOL_SIZE:
        raise SourceError(
            f"Rotation pool '{pool}' requires at least {_MIN_POOL_SIZE} successful symbols"
        )
    items, inactive = _cross_section(pool, current, histories)
    counts = Counter(item.stage for item in items)
    return (
        items,
        RotationPoolSummary(
            pool=pool,
            as_of=as_of,
            total=len(symbols),
            analyzed=len(current),
            failed=len(failures),
            emerging=counts["emerging"],
            strong=counts["strong"],
            fading=counts["fading"],
            inactive=inactive,
        ),
        failures,
    )


def rotate_pools(source_groups: list[str]) -> RotationResult:
    """Analyze multiple Longport groups with absolute stages and pool-local ranking."""
    if len(source_groups) < 1 or len(set(source_groups)) != len(source_groups):
        raise StkError("Rotation source groups must be unique")
    pools: list[tuple[str, list[tuple[str, str]]]] = []
    seen: dict[str, str] = {}
    for group in source_groups:
        watchlist = get_watchlist(group)
        symbols = [(item.symbol, item.name) for item in watchlist.securities]
        for symbol, _ in symbols:
            normalized = to_longport_symbol(symbol)
            if previous_pool := seen.get(normalized):
                raise StkError(
                    f"Duplicate symbol {normalized} in source pools '{previous_pool}' and '{group}'"
                )
            seen[normalized] = group
        pools.append((group, symbols))

    all_items: list[RotationItem] = []
    summaries: list[RotationPoolSummary] = []
    failures: list[RotationFailure] = []
    for group, symbols in pools:
        items, summary, pool_failures = _analyze_pool(group, symbols)
        all_items.extend(items)
        summaries.append(summary)
        failures.extend(pool_failures)
    by_stage = {
        stage: [item for item in all_items if item.stage == stage]
        for stage in ("emerging", "strong", "fading")
    }
    setup_rank: dict[RotationSetup | None, int] = {"confirmed": 0, "rebound": 1, None: 2}
    severity_rank: dict[FadeSeverity | None, int] = {
        "severe": 0,
        "confirmed": 1,
        "mild": 2,
        None: 3,
    }
    by_stage["emerging"].sort(
        key=lambda item: (
            setup_rank[item.setup],
            item.signal.supertrend_bullish_age or 0,
            -item.rank_score,
            item.symbol,
        )
    )
    by_stage["strong"].sort(key=lambda item: (-item.rank_score, item.symbol))
    by_stage["fading"].sort(
        key=lambda item: (severity_rank[item.fade_severity], -item.rank_score, item.symbol)
    )
    sorted_failures = sorted(failures, key=lambda item: (item.pool, item.symbol or ""))
    return RotationResult(
        sources=summaries,
        summary=RotationSummary(
            total=sum(item.total for item in summaries),
            analyzed=sum(item.analyzed for item in summaries),
            failed=len(failures),
            emerging=len(by_stage["emerging"]),
            strong=len(by_stage["strong"]),
            fading=len(by_stage["fading"]),
            inactive=sum(item.inactive for item in summaries),
        ),
        emerging=by_stage["emerging"],
        strong=by_stage["strong"],
        fading=by_stage["fading"],
        failures=sorted_failures,
    )


def _rollback_rotation_targets(
    written: list[tuple[str, list[str]]],
    previous: dict[str, list[str]],
) -> list[str]:
    """Restore groups written before a routing failure; return rollback errors."""
    rollback_failures: list[str] = []
    for group, _ in written:
        try:
            add_symbols(group, previous[group], mode=SecuritiesUpdateMode.Replace)
        except Exception as err:
            rollback_failures.append(f"{group}: {err}")
    return rollback_failures


def route_rotation(
    sources: list[str],
    *,
    emerging: str,
    strong: str,
    fading: str,
) -> RotationRouteResult:
    """Calculate fully, then replace all three destination snapshots.

    The three Replace writes are not atomic on their own: if a later write
    fails, groups written earlier are rolled back to their pre-route contents
    so the snapshot set stays consistent.
    """
    targets = [emerging, strong, fading]
    if len({*sources, *targets}) != len(sources) + len(targets):
        raise StkError("Rotation source and target groups must all be different")
    result = rotate_pools(sources)
    stage_items = [result.emerging, result.strong, result.fading]
    stage_names: list[RotationStage] = ["emerging", "strong", "fading"]

    # Snapshot current contents up front so a mid-write failure can roll back
    # groups that were already replaced.
    previous: dict[str, list[str]] = {}
    for group in targets:
        try:
            previous[group] = sorted(item.symbol for item in get_watchlist(group).securities)
        except SourceError:
            previous[group] = []

    route_targets: list[RotationRouteTarget] = []
    written: list[tuple[str, list[str]]] = []
    try:
        for stage, group, items in zip(stage_names, targets, stage_items, strict=True):
            symbols = [item.symbol for item in items]
            add_symbols(group, symbols, mode=SecuritiesUpdateMode.Replace)
            written.append((group, symbols))
            route_targets.append(RotationRouteTarget(stage=stage, group=group, symbols=symbols))
    except Exception as err:
        rollback_failures = _rollback_rotation_targets(written, previous)
        detail = (
            f"；已回滚 {len(written)} 个已写入目标组"
            if not rollback_failures
            else f"；回滚失败（目标组可能不一致）：{'；'.join(rollback_failures)}"
        )
        raise StkError(f"轮动路由写入失败：{err}{detail}") from err
    return RotationRouteResult(**result.model_dump(), targets=route_targets)
