"""Current-state daily signal assessment service."""

from datetime import datetime
from typing import cast

import numpy as np
import pandas as pd
from stockstats import StockDataFrame
import talib

from stk.errors import IndicatorError
from stk.models.score import (
    AssessmentState,
    ContextBias,
    ContextFactor,
    FactorState,
    MetricValue,
    QualitySummary,
    RecentSignalBar,
    SignalIndicators,
    SignalRisk,
    SignalTrigger,
    StockAssessment,
    TrendDirection,
)
from stk.services.history import candles_to_df, get_history
from stk.services.indicator import (
    _calc_kdj_arrays,
    _calc_supertrend_arrays,
    _to_stock_frame,
)
from stk.utils.symbol import to_longport_symbol
from stk.utils.trading_session import is_unclosed_daily_bar

_EMA_FAST = 9
_EMA_SLOW = 26
_MIN_HISTORY = 30
_RSI_PERIOD = 14
_ADX_PERIOD = 14
_MFI_PERIOD = 14
_MACD_FAST = 12
_MACD_SLOW = 26
_MACD_SIGNAL = 9
_BOLL_PERIOD = 20
_BOLL_NBDEV = 2
_DIVERGENCE_LOOKBACK = 20
_ROUTING_TRIGGER_WINDOW = 3
_ENTRY_RSI_OVERHEATED = 75
_ENTRY_ATR_EXTENSION = 1.5


def _closed_daily_df(
    df: pd.DataFrame,
    symbol: str,
    *,
    now: datetime | None = None,
) -> pd.DataFrame:
    if df.empty:
        return df
    if is_unclosed_daily_bar(df.iloc[-1]["date"], symbol, now=now):
        return df.iloc[:-1].copy()
    return df


def _safe_value(series: np.ndarray, index: int = -1) -> float | None:
    value = series[index]
    return None if np.isnan(value) else round(float(value), 4)


def _clean_metrics(metrics: dict[str, MetricValue]) -> dict[str, MetricValue]:
    return {key: value for key, value in metrics.items() if value is not None}


def _factor_state_for_direction(
    *,
    bullish: bool,
    bearish: bool,
    direction: TrendDirection,
) -> FactorState:
    if direction == "bullish":
        if bullish:
            return "confirming"
        if bearish:
            return "conflicting"
    elif direction == "bearish":
        if bearish:
            return "confirming"
        if bullish:
            return "conflicting"
    return "neutral"


def _momentum_factor(
    close: pd.Series,
    stock: StockDataFrame,
    *,
    direction: TrendDirection,
) -> ContextFactor:
    rsi = talib.RSI(close.to_numpy(dtype=float), timeperiod=_RSI_PERIOD)
    rsi_now = _safe_value(rsi)
    k, d, j = _calc_kdj_arrays(stock)
    k_now, d_now, j_now = _safe_value(k), _safe_value(d), _safe_value(j)

    oversold = (rsi_now is not None and rsi_now < 30) or (j_now is not None and j_now < 20)
    overbought = (rsi_now is not None and rsi_now > 70) or (j_now is not None and j_now > 80)
    if oversold:
        state: FactorState = "opportunity"
    elif overbought:
        state = "risk"
    else:
        state = _factor_state_for_direction(
            bullish=k_now is not None and d_now is not None and k_now > d_now,
            bearish=k_now is not None and d_now is not None and k_now < d_now,
            direction=direction,
        )
    return ContextFactor(
        name="momentum",
        state=state,
        metrics=_clean_metrics({
            "rsi14": rsi_now,
            "k": k_now,
            "d": d_now,
            "j": j_now,
        }),
    )


def _macd_factor(
    close: np.ndarray,
    *,
    direction: TrendDirection,
) -> tuple[ContextFactor, np.ndarray]:
    dif, dea, hist = talib.MACD(
        close,
        fastperiod=_MACD_FAST,
        slowperiod=_MACD_SLOW,
        signalperiod=_MACD_SIGNAL,
    )
    dif_now, dea_now, hist_now = _safe_value(dif), _safe_value(dea), _safe_value(hist)
    bullish = (
        dif_now is not None
        and dea_now is not None
        and hist_now is not None
        and dif_now > dea_now
        and hist_now > 0
    )
    bearish = (
        dif_now is not None
        and dea_now is not None
        and hist_now is not None
        and dif_now < dea_now
        and hist_now < 0
    )
    return (
        ContextFactor(
            name="macd",
            state=_factor_state_for_direction(
                bullish=bullish,
                bearish=bearish,
                direction=direction,
            ),
            metrics=_clean_metrics({"dif": dif_now, "dea": dea_now, "hist": hist_now}),
        ),
        hist,
    )


def _boll_factor(
    close: np.ndarray,
    current_price: float,
    *,
    direction: TrendDirection,
) -> tuple[ContextFactor, list[str]]:
    upper, middle, lower = talib.BBANDS(
        close,
        timeperiod=_BOLL_PERIOD,
        nbdevup=_BOLL_NBDEV,
        nbdevdn=_BOLL_NBDEV,
    )
    upper_now, middle_now, lower_now = (
        _safe_value(upper),
        _safe_value(middle),
        _safe_value(lower),
    )
    if upper_now is None or middle_now is None or lower_now is None:
        return ContextFactor(name="boll", state="none"), []

    bandwidth = upper_now - lower_now
    position = (current_price - lower_now) / bandwidth * 100 if bandwidth > 0 else 50
    bandwidth_pct = bandwidth / middle_now * 100 if middle_now > 0 else 999
    warnings = [f"布林收窄（带宽 {bandwidth_pct:.1f}%）"] if bandwidth_pct < 5 else []
    if position < 10:
        state: FactorState = "opportunity"
    elif position >= 95:
        state = "risk"
    else:
        state = _factor_state_for_direction(
            bullish=position >= 50,
            bearish=position < 50,
            direction=direction,
        )
    return (
        ContextFactor(
            name="boll",
            state=state,
            metrics={
                "upper": upper_now,
                "middle": middle_now,
                "lower": lower_now,
                "position_pct": round(position, 1),
                "bandwidth_pct": round(bandwidth_pct, 1),
            },
        ),
        warnings,
    )


def _turnover_ratio(df: pd.DataFrame) -> float | None:
    if "turnover" not in df.columns or len(df) < 6:
        return None
    turnover = df["turnover"].astype(float)
    average = turnover.iloc[-6:-1].mean()
    return round(float(turnover.iloc[-1] / average), 2) if average > 0 else None


def _volume_factor(
    df: pd.DataFrame,
    close: pd.Series,
    *,
    direction: TrendDirection,
) -> ContextFactor:
    ratio = _turnover_ratio(df)
    if ratio is None:
        return ContextFactor(name="volume_price", state="none")
    previous = float(close.iloc[-2])
    change = (float(close.iloc[-1]) - previous) / previous * 100 if previous > 0 else 0
    if ratio > 2 and change < -3:
        state: FactorState = "risk"
    else:
        state = _factor_state_for_direction(
            bullish=ratio > 1.5 and change > 1,
            bearish=ratio > 1.5 and change < -1,
            direction=direction,
        )
    return ContextFactor(
        name="volume_price",
        state=state,
        metrics={"turnover_ratio_5d": ratio, "price_change_pct": round(change, 2)},
    )


def _ema_factor(
    close: np.ndarray,
    current_price: float,
    *,
    direction: TrendDirection,
) -> ContextFactor:
    ema5 = _safe_value(talib.EMA(close, timeperiod=5))
    ema10 = _safe_value(talib.EMA(close, timeperiod=10))
    ema20 = _safe_value(talib.EMA(close, timeperiod=20))
    if ema5 is None or ema10 is None or ema20 is None:
        return ContextFactor(name="ema_trend", state="none")
    bullish = ema5 > ema10 > ema20 and current_price > ema5
    bearish = ema5 < ema10 < ema20 and current_price < ema5
    return ContextFactor(
        name="ema_trend",
        state=_factor_state_for_direction(
            bullish=bullish,
            bearish=bearish,
            direction=direction,
        ),
        metrics={
            "ema5": ema5,
            "ema10": ema10,
            "ema20": ema20,
            "arrangement": "bullish" if bullish else "bearish" if bearish else "none",
        },
    )


def _money_flow_factor(
    df: pd.DataFrame,
    *,
    direction: TrendDirection,
) -> ContextFactor:
    mfi = talib.MFI(
        df["high"].to_numpy(dtype=float),
        df["low"].to_numpy(dtype=float),
        df["close"].to_numpy(dtype=float),
        df["volume"].to_numpy(dtype=float),
        timeperiod=_MFI_PERIOD,
    )
    value = _safe_value(mfi)
    if value is None:
        return ContextFactor(name="money_flow", state="none")
    if value < 20:
        state: FactorState = "opportunity"
    elif value > 80:
        state = "risk"
    elif direction == "bullish":
        state = "confirming" if value > 60 else "conflicting" if value < 40 else "neutral"
    elif direction == "bearish":
        state = "confirming" if value < 40 else "conflicting" if value > 60 else "neutral"
    else:
        state = "opportunity" if value < 40 else "risk" if value > 60 else "neutral"
    return ContextFactor(name="money_flow", state=state, metrics={"mfi14": value})


def _divergence_factor(close: pd.Series, hist: np.ndarray) -> ContextFactor:
    lookback = _DIVERGENCE_LOOKBACK
    if len(close) < lookback + 1 or np.isnan(hist[-1]):
        return ContextFactor(name="divergence", state="none")
    prior_close = close.iloc[-(lookback + 1) : -1]
    prior_hist = hist[-(lookback + 1) : -1]
    current_close = float(close.iloc[-1])
    current_hist = float(hist[-1])
    low_index = int(prior_close.to_numpy().argmin())
    high_index = int(prior_close.to_numpy().argmax())
    low_hist = prior_hist[low_index]
    high_hist = prior_hist[high_index]
    if (
        not np.isnan(low_hist)
        and current_close <= float(prior_close.iloc[low_index]) * 1.02
        and current_hist > low_hist
    ):
        return ContextFactor(
            name="divergence",
            state="opportunity",
            metrics={"type": "macd_bullish", "lookback": lookback},
        )
    if (
        not np.isnan(high_hist)
        and current_close >= float(prior_close.iloc[high_index]) * 0.98
        and current_hist < high_hist
    ):
        return ContextFactor(
            name="divergence",
            state="risk",
            metrics={"type": "macd_bearish", "lookback": lookback},
        )
    return ContextFactor(
        name="divergence",
        state="none",
        metrics={"type": "none", "lookback": lookback},
    )


def _overall_bias(factors: list[ContextFactor]) -> ContextBias:
    confirming = sum(factor.state == "confirming" for factor in factors)
    conflicting = sum(factor.state == "conflicting" for factor in factors)
    risky = sum(factor.state == "risk" for factor in factors)
    if conflicting >= 2 or conflicting > confirming:
        return "conflicting"
    if risky >= 2 or (risky > 0 and confirming < 2):
        return "risky"
    if confirming >= 2 and conflicting == 0:
        return "supportive"
    return "mixed"


def _quality(
    df: pd.DataFrame,
    stock: StockDataFrame,
    close: np.ndarray,
    *,
    direction: TrendDirection,
    include_factors: bool,
) -> QualitySummary:
    close_series = cast(pd.Series, df["close"])
    macd, hist = _macd_factor(close, direction=direction)
    boll, warnings = _boll_factor(close, float(close[-1]), direction=direction)
    factors = [
        _momentum_factor(close_series, stock, direction=direction),
        macd,
        boll,
        _volume_factor(df, close_series, direction=direction),
        _ema_factor(close, float(close[-1]), direction=direction),
        _money_flow_factor(df, direction=direction),
        _divergence_factor(close_series, hist),
    ]
    return QualitySummary(
        bias=_overall_bias(factors),
        warnings=warnings,
        factors=factors if include_factors else None,
    )


def _last_supertrend_flip_age(direction: np.ndarray, *, target: int) -> int | None:
    last_index: int | None = None
    for index in range(1, len(direction)):
        if (
            direction[index - 1] != 0
            and direction[index] == target
            and direction[index - 1] != target
        ):
            last_index = index
    return None if last_index is None else len(direction) - 1 - last_index


def _recent_bars(
    df: pd.DataFrame,
    *,
    count: int,
    ema9: np.ndarray,
    ema26: np.ndarray,
    rsi: np.ndarray,
    atr: np.ndarray,
    supertrend: np.ndarray,
    direction: np.ndarray,
) -> list[RecentSignalBar] | None:
    if count <= 0:
        return None
    start = max(0, len(df) - count)
    bars: list[RecentSignalBar] = []
    for index in range(start, len(df)):
        row = df.iloc[index]
        trend: TrendDirection | None
        if direction[index] > 0:
            trend = "bullish"
        elif direction[index] < 0:
            trend = "bearish"
        else:
            trend = None
        bars.append(
            RecentSignalBar(
                date=str(row["date"]),
                open=round(float(row["open"]), 4),
                high=round(float(row["high"]), 4),
                low=round(float(row["low"]), 4),
                close=round(float(row["close"]), 4),
                volume=int(row["volume"]),
                turnover=round(float(row["turnover"]), 4),
                ema9=_safe_value(ema9, index),
                ema26=_safe_value(ema26, index),
                rsi14=_safe_value(rsi, index),
                atr10=_safe_value(atr, index),
                supertrend=_safe_value(supertrend, index),
                supertrend_direction=trend,
            )
        )
    return bars


def calc_score(
    symbol: str,
    *,
    count: int = 60,
    recent_bars: int = 0,
    include_factors: bool = False,
) -> StockAssessment:
    """Calculate the single current daily assessment for one symbol."""
    candles = get_history(symbol, count=max(count, recent_bars))
    if not candles:
        raise IndicatorError(f"Insufficient history for {symbol} (need>={_MIN_HISTORY}, got 0)")
    df = _closed_daily_df(candles_to_df(candles), symbol)
    if len(df) < _MIN_HISTORY:
        raise IndicatorError(
            f"Insufficient closed daily history for {symbol} (need>={_MIN_HISTORY}, got {len(df)})"
        )

    close = df["close"].to_numpy(dtype=float)
    current_close = round(float(close[-1]), 4)
    ema9_array = talib.EMA(close, timeperiod=_EMA_FAST)
    ema26_array = talib.EMA(close, timeperiod=_EMA_SLOW)
    rsi_array = talib.RSI(close, timeperiod=_RSI_PERIOD)
    adx_array = talib.ADX(
        df["high"].to_numpy(dtype=float),
        df["low"].to_numpy(dtype=float),
        close,
        timeperiod=_ADX_PERIOD,
    )
    stock = _to_stock_frame(df)
    supertrend_array, direction_array, atr_array = _calc_supertrend_arrays(stock)

    ema9 = _safe_value(ema9_array)
    ema26 = _safe_value(ema26_array)
    rsi = _safe_value(rsi_array)
    atr = _safe_value(atr_array)
    supertrend = _safe_value(supertrend_array)
    if (
        ema9 is None
        or ema26 is None
        or rsi is None
        or atr is None
        or atr <= 0
        or supertrend is None
        or direction_array[-1] == 0
    ):
        raise IndicatorError(f"Core indicators are not available for {symbol}")

    trend_direction: TrendDirection = "bullish" if direction_array[-1] > 0 else "bearish"
    max_entry_price = round(ema9 + _ENTRY_ATR_EXTENSION * atr, 4)
    turnover_ratio = _turnover_ratio(df)

    buy_triggers: list[SignalTrigger] = []
    if current_close >= ema9 and 45 <= rsi < 70:
        buy_triggers.append("healthy_continuation")
    if ema26 <= current_close <= ema9 and rsi >= 40 and current_close > float(close[-2]):
        buy_triggers.append("pullback_hold")
    for age in range(min(_ROUTING_TRIGGER_WINDOW, len(rsi_array) - 1)):
        index = len(rsi_array) - 1 - age
        if (
            not np.isnan(rsi_array[index - 1])
            and not np.isnan(rsi_array[index])
            and rsi_array[index - 1] < 50 <= rsi_array[index]
            and rsi >= 50
        ):
            buy_triggers.append("momentum_recovery")
            break
    bull_flip_age = _last_supertrend_flip_age(direction_array, target=1)
    if bull_flip_age is not None and bull_flip_age < _ROUTING_TRIGGER_WINDOW:
        buy_triggers.append("trend_start")

    sell_triggers: list[SignalTrigger] = []
    if direction_array[-1] < 0:
        sell_triggers.append("supertrend_bearish")
    if not np.isnan(ema26_array[-2]) and close[-2] < ema26_array[-2] and current_close < ema26:
        sell_triggers.append("ema26_breakdown")
    if (
        not np.isnan(rsi_array[-2])
        and rsi_array[-2] >= _ENTRY_RSI_OVERHEATED
        and rsi < rsi_array[-2]
        and current_close < ema9
    ):
        sell_triggers.append("overheat_reversal")

    entry_baseline = (
        ema9 > ema26
        and direction_array[-1] > 0
        and current_close >= ema26
        and rsi < _ENTRY_RSI_OVERHEATED
        and current_close <= max_entry_price
    )
    reasons: list[str] = []
    if sell_triggers:
        state: AssessmentState = "sell"
        reason_labels = {
            "supertrend_bearish": "Supertrend 已转为空头",
            "ema26_breakdown": "连续两根收盘价低于 EMA26",
            "overheat_reversal": "RSI 从过热区回落且收盘价跌破 EMA9",
        }
        reasons.extend(reason_labels[trigger] for trigger in sell_triggers)
        triggers = sell_triggers
    elif entry_baseline and buy_triggers:
        state = "buy"
        reason_labels = {
            "healthy_continuation": "多头结构健康延续",
            "pullback_hold": "回踩 EMA 区间后企稳",
            "momentum_recovery": "最近三根日线内 RSI 上穿 50",
            "trend_start": "最近三根日线内 Supertrend 翻多",
        }
        reasons.extend(reason_labels[trigger] for trigger in buy_triggers)
        triggers = buy_triggers
    elif ema9 > ema26 or direction_array[-1] > 0:
        state = "watch"
        triggers = []
        if rsi >= _ENTRY_RSI_OVERHEATED:
            reasons.append(f"RSI14={rsi:.2f} 已过热")
        elif current_close > max_entry_price:
            reasons.append("价格高于 EMA9 + 1.5xATR10")
        elif current_close < ema26:
            reasons.append("收盘价低于 EMA26")
        else:
            reasons.append("趋势部分成立，但尚无有效买入触发")
    else:
        state = "ignored"
        triggers = []
        reasons.append("当前未形成买入或卖出信号")

    if turnover_ratio is not None and turnover_ratio < 0.8:
        reasons.append(f"5 日成交额量比 {turnover_ratio:.2f}，量能偏弱")

    quality_direction: TrendDirection
    if state == "buy":
        quality_direction = "bullish"
    elif state == "sell":
        quality_direction = "bearish"
    else:
        quality_direction = "neutral"

    risk = None
    if state == "buy":
        fallback_stop = current_close - atr * 2
        trailing_stop = (
            supertrend if trend_direction == "bullish" and supertrend < current_close else None
        )
        risk = SignalRisk(
            stop_loss=round(max(trailing_stop or fallback_stop, fallback_stop), 4),
            trailing_stop=trailing_stop,
        )

    return StockAssessment(
        symbol=to_longport_symbol(symbol),
        as_of=str(df.iloc[-1]["date"]),
        state=state,
        triggers=triggers,
        reasons=reasons,
        indicators=SignalIndicators(
            close=current_close,
            ema9=ema9,
            ema26=ema26,
            supertrend=supertrend,
            supertrend_direction=trend_direction,
            rsi14=rsi,
            atr10=atr,
            adx14=_safe_value(adx_array),
            turnover_ratio_5d=turnover_ratio,
            max_entry_price=max_entry_price if state == "buy" else None,
        ),
        quality=_quality(
            df,
            stock,
            close,
            direction=quality_direction,
            include_factors=include_factors,
        ),
        risk=risk,
        recent_bars=_recent_bars(
            df,
            count=recent_bars,
            ema9=ema9_array,
            ema26=ema26_array,
            rsi=rsi_array,
            atr=atr_array,
            supertrend=supertrend_array,
            direction=direction_array,
        ),
    )
