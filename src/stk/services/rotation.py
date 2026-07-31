"""ETF cross-sectional rotation analysis and Longport snapshot routing."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import math
from typing import cast

from longport.openapi import SecuritiesUpdateMode
import numpy as np
import pandas as pd
from stockstats import StockDataFrame, set_dft_window, wrap
import talib

from stk.errors import IndicatorError, SourceError, StkError, error_code
from stk.models.rotation import (
    RotationAction,
    RotationFactors,
    RotationFailure,
    RotationIndicators,
    RotationItem,
    RotationPoolSummary,
    RotationResult,
    RotationRouteResult,
    RotationRouteTarget,
    RotationSignal,
    RotationStage,
    RotationSummary,
    RotationTrend,
)
from stk.services.history import candles_to_df, get_history
from stk.services.watchlist import add_symbols, get_watchlist
from stk.utils.symbol import to_longport_symbol
from stk.utils.trading_session import is_unclosed_daily_bar

_MIN_BARS = 70
_HISTORY_BARS = 90
_MIN_POOL_SIZE = 5
set_dft_window("supertrend", 10)


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
    supertrend_direction: np.ndarray


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


def _indicator_point(series: _Series, index: int) -> _Point:
    frame = series.frame.iloc[: index + 1]
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
    stock.SUPERTREND_MUL = 3
    supertrend = stock["supertrend"].to_numpy(dtype=float)
    upper = stock["supertrend_ub"].to_numpy(dtype=float)
    lower = stock["supertrend_lb"].to_numpy(dtype=float)
    atr10 = stock["atr_10"].to_numpy(dtype=float)
    separated = ~np.isclose(upper, lower)
    direction = np.zeros(len(supertrend), dtype=int)
    direction[np.isclose(supertrend, lower) & separated] = 1
    direction[np.isclose(supertrend, upper) & separated] = -1

    arrays = {
        "return5": talib.ROCP(close, timeperiod=5),
        "return20": talib.ROCP(close, timeperiod=20),
        "return60": talib.ROCP(close, timeperiod=60),
        "vol20": talib.STDDEV(log_return, timeperiod=20) * math.sqrt(20),
        "vol60": talib.STDDEV(log_return, timeperiod=60) * math.sqrt(60),
        "slope20": talib.LINEARREG_SLOPE(log_close, timeperiod=20),
        "correlation20": talib.CORREL(log_close, time_index, timeperiod=20),
        "ema9": talib.EMA(close, timeperiod=9),
        "ema20": talib.EMA(close, timeperiod=20),
        "ema26": talib.EMA(close, timeperiod=26),
        "ema60": talib.EMA(close, timeperiod=60),
        "rsi14": talib.RSI(close, timeperiod=14),
        "mfi14": talib.MFI(high, low, close, volume, timeperiod=14),
    }
    values = {key: _finite(values[-1], key) for key, values in arrays.items()}
    values["previous_return5"] = _finite(arrays["return5"][-6], "previous_return5")
    values["close"] = float(close[-1])
    values["atr10"] = _finite(atr10[-1], "atr10")
    values["supertrend"] = _finite(supertrend[-1], "supertrend")
    turnover = frame["turnover"].to_numpy(dtype=float)
    previous_turnover = float(np.mean(turnover[-25:-5]))
    values["turnover_ratio"] = (
        float(np.mean(turnover[-5:])) / previous_turnover if previous_turnover > 0 else 1.0
    )
    return _Point(series=series, index=index, metrics=values, supertrend_direction=direction)


def percentile(values: pd.Series) -> pd.Series:
    """Return pool percentiles with ties sharing their average rank."""
    valid = values.dropna()
    if len(valid) <= 1:
        return pd.Series(50.0, index=values.index)
    result = (values.rank(method="average") - 1) / (len(valid) - 1) * 100
    return result.fillna(50.0)


def classify_stage(strength: float, momentum: float) -> RotationStage:
    """Map strength and momentum to one mutually exclusive buffered stage."""
    if strength <= 50:
        return "emerging" if momentum >= 55 else "lagging"
    return "leading" if momentum >= 45 else "weakening"


def _events(point: _Point) -> RotationSignal:
    values = point.metrics
    frame = point.series.frame.iloc[: point.index + 1]
    close = frame["close"].to_numpy(dtype=float)
    ema9 = talib.EMA(close, timeperiod=9)
    ema26 = talib.EMA(close, timeperiod=26)
    direction = point.supertrend_direction
    start = max(1, len(close) - 3)
    st_bull = any(direction[i - 1] < 0 and direction[i] > 0 for i in range(start, len(close)))
    st_bear = any(direction[i - 1] > 0 and direction[i] < 0 for i in range(start, len(close)))
    golden = any(
        ema9[i - 1] <= ema26[i - 1] and ema9[i] > ema26[i] for i in range(start, len(close))
    )
    death = any(
        ema9[i - 1] >= ema26[i - 1] and ema9[i] < ema26[i] for i in range(start, len(close))
    )
    entry = (
        values["close"] > values["ema20"]
        and (direction[-1] > 0 or values["ema9"] > values["ema26"])
        and values["rsi14"] < 75
        and values["close"] <= values["ema20"] + 2 * values["atr10"]
    )
    return RotationSignal(
        supertrend_bullish_event=st_bull,
        supertrend_bearish_event=st_bear,
        ema_golden_cross=golden,
        ema_death_cross=death,
        entry_eligible=entry,
    )


def determine_action(
    stage: RotationStage,
    momentum: float,
    trend: RotationTrend,
    signal: RotationSignal,
    *,
    supertrend_bullish: bool,
    ema_bullish: bool,
) -> RotationAction:
    """Apply the six-action priority matrix."""
    bearish_event = (signal.supertrend_bearish_event and not supertrend_bullish) or (
        signal.ema_death_cross and not ema_bullish
    )
    bullish_event = (signal.supertrend_bullish_event and supertrend_bullish) or (
        signal.ema_golden_cross and ema_bullish
    )
    if stage in ("weakening", "lagging") and bearish_event:
        return "exit"
    if (
        stage in ("emerging", "leading")
        and momentum >= 55
        and bullish_event
        and signal.entry_eligible
    ):
        return "rotate_in"
    if stage == "leading" and trend == "bullish" and not bearish_event:
        return "hold"
    if stage == "weakening":
        return "reduce"
    if stage in ("emerging", "leading"):
        return "watch"
    return "avoid"


def _cross_section(
    pool: str,
    points: list[_Point],
    *,
    previous_stages: dict[str, RotationStage] | None = None,
) -> list[RotationItem]:
    table = pd.DataFrame(
        [point.metrics for point in points], index=[p.series.symbol for p in points]
    )
    vol20_floor = float(table["vol20"].quantile(0.1))
    vol60_floor = float(table["vol60"].quantile(0.1))
    adjusted20 = table["vol20"].clip(lower=max(vol20_floor, np.finfo(float).eps))
    adjusted60 = table["vol60"].clip(lower=max(vol60_floor, np.finfo(float).eps))
    excess5 = table["return5"] - table["return5"].median()
    previous_excess5 = table["previous_return5"] - table["previous_return5"].median()
    table["rm20"] = (table["return20"] - table["return20"].median()) / adjusted20
    table["rm60"] = (table["return60"] - table["return60"].median()) / adjusted60
    table["quality"] = table["slope20"] * table["correlation20"].pow(2) / adjusted20
    table["acceleration"] = (excess5 - previous_excess5) / adjusted20
    table["turnover_confirmation"] = np.sign(excess5) * np.log(
        table["turnover_ratio"].clip(lower=np.finfo(float).eps)
    )
    table["mfi_confirmation"] = (table["mfi14"] - 50) / 50
    table["strength"] = (
        percentile(table["rm20"]) * 0.50
        + percentile(table["rm60"]) * 0.35
        + percentile(table["quality"]) * 0.15
    )
    table["volume_confirmation"] = (
        percentile(table["turnover_confirmation"]) * 0.70
        + percentile(table["mfi_confirmation"]) * 0.30
    )
    table["momentum"] = (
        percentile(table["acceleration"]) * 0.80 + table["volume_confirmation"] * 0.20
    )
    mean_turnovers = pd.Series({
        point.series.symbol: float(
            point.series.frame.iloc[: point.index + 1]["turnover"].tail(20).mean()
        )
        for point in points
    })
    liquidity_cutoff = float(mean_turnovers.quantile(0.2))

    items: list[RotationItem] = []
    for point in points:
        symbol = point.series.symbol
        row = table.loc[symbol]
        strength = float(row["strength"])
        momentum = float(row["momentum"])
        stage = classify_stage(strength, momentum)
        values = point.metrics
        current_st = point.supertrend_direction[-1] > 0
        ema_bullish = values["ema9"] > values["ema26"]
        if values["close"] > values["ema20"] > values["ema60"] and current_st:
            trend: RotationTrend = "bullish"
        elif values["close"] < values["ema20"] < values["ema60"] and not current_st:
            trend = "bearish"
        else:
            trend = "neutral"
        signal = _events(point)
        previous_stage = previous_stages.get(symbol) if previous_stages else None
        items.append(
            RotationItem(
                pool=pool,
                symbol=symbol,
                name=point.series.name,
                as_of=str(point.series.frame.iloc[point.index]["date"]),
                stage=stage,
                previous_stage=previous_stage,
                stage_changed=previous_stage is not None and previous_stage != stage,
                action=determine_action(
                    stage,
                    momentum,
                    trend,
                    signal,
                    supertrend_bullish=current_st,
                    ema_bullish=ema_bullish,
                ),
                trend=trend,
                strength=round(strength, 4),
                momentum=round(momentum, 4),
                factors=RotationFactors(
                    return5=values["return5"],
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
                    relative_momentum20=float(row["rm20"]),
                    relative_momentum60=float(row["rm60"]),
                    trend_quality=float(row["quality"]),
                    acceleration=float(row["acceleration"]),
                    turnover_ratio=values["turnover_ratio"],
                    turnover_confirmation=float(row["turnover_confirmation"]),
                    mfi_confirmation=float(row["mfi_confirmation"]),
                    volume_confirmation=float(row["volume_confirmation"]),
                ),
                indicators=RotationIndicators(
                    close=values["close"],
                    ema9=values["ema9"],
                    ema20=values["ema20"],
                    ema26=values["ema26"],
                    ema60=values["ema60"],
                    rsi14=values["rsi14"],
                    mfi14=values["mfi14"],
                    atr10=values["atr10"],
                    atr_pct=values["atr10"] / values["close"] * 100,
                    supertrend=values["supertrend"],
                    supertrend_bullish=current_st,
                ),
                signal=signal,
                warnings=(["low_liquidity"] if mean_turnovers[symbol] <= liquidity_cutoff else []),
            )
        )
    return items


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
    previous: list[_Point] = []
    for item in aligned:
        try:
            current_point = _indicator_point(item, len(item.frame) - 1)
            previous_point = _indicator_point(item, len(item.frame) - 2)
            current.append(current_point)
            previous.append(previous_point)
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
    previous_items = _cross_section(pool, previous)
    previous_stages = {item.symbol: item.stage for item in previous_items}
    items = _cross_section(pool, current, previous_stages=previous_stages)
    counts = Counter(item.stage for item in items)
    return (
        items,
        RotationPoolSummary(
            pool=pool,
            as_of=as_of,
            total=len(symbols),
            analyzed=len(items),
            failed=len(failures),
            emerging=counts["emerging"],
            leading=counts["leading"],
            weakening=counts["weakening"],
            lagging=counts["lagging"],
        ),
        failures,
    )


def rotate_pools(source_groups: list[str]) -> RotationResult:
    """Analyze multiple Longport groups, ranking each independently."""
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
        stage: [i for i in all_items if i.stage == stage]
        for stage in ("emerging", "leading", "weakening", "lagging")
    }
    by_stage["emerging"].sort(key=lambda item: (-item.momentum, -item.strength))
    by_stage["leading"].sort(key=lambda item: (-item.strength, -item.momentum))
    by_stage["weakening"].sort(key=lambda item: (item.momentum, -item.strength))
    by_stage["lagging"].sort(key=lambda item: (item.strength, item.momentum))
    sorted_failures: list[RotationFailure] = sorted(
        failures, key=lambda item: (item.pool, item.symbol or "")
    )
    return RotationResult(
        sources=summaries,
        summary=RotationSummary(
            total=sum(item.total for item in summaries),
            analyzed=len(all_items),
            failed=len(failures),
            emerging=len(by_stage["emerging"]),
            leading=len(by_stage["leading"]),
            weakening=len(by_stage["weakening"]),
            lagging=len(by_stage["lagging"]),
        ),
        emerging=by_stage["emerging"],
        leading=by_stage["leading"],
        weakening=by_stage["weakening"],
        lagging=by_stage["lagging"],
        failures=sorted_failures,
    )


def route_rotation(
    sources: list[str],
    *,
    emerging: str,
    leading: str,
    weakening: str,
    lagging: str,
) -> RotationRouteResult:
    """Calculate fully, then replace all four shared destination snapshots."""
    targets = [emerging, leading, weakening, lagging]
    if len({*sources, *targets}) != len(sources) + len(targets):
        raise StkError("Rotation source and target groups must all be different")
    result = rotate_pools(sources)
    stage_items = [result.emerging, result.leading, result.weakening, result.lagging]
    stage_names: list[RotationStage] = ["emerging", "leading", "weakening", "lagging"]
    route_targets: list[RotationRouteTarget] = []
    for stage, group, items in zip(stage_names, targets, stage_items, strict=True):
        symbols = [item.symbol for item in items]
        add_symbols(group, symbols, mode=SecuritiesUpdateMode.Replace)
        route_targets.append(RotationRouteTarget(stage=stage, group=group, symbols=symbols))
    return RotationRouteResult(**result.model_dump(), targets=route_targets)
