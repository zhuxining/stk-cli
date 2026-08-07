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
    SignalConfirmation,
    SignalIndicators,
    SignalRisk,
    SignalTrigger,
    SignalTriggerCode,
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
_BUY_TRIGGER_WINDOW = 2
_SELL_TRIGGER_WINDOW = 2
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


def _supertrend_flip_indices(direction: np.ndarray, *, target: int) -> list[int]:
    indices: list[int] = []
    for index in range(1, len(direction)):
        if (
            direction[index - 1] != 0
            and direction[index] == target
            and direction[index - 1] != target
        ):
            indices.append(index)
    return indices


def _ema_cross_indices(
    fast: np.ndarray,
    slow: np.ndarray,
    *,
    bullish: bool,
) -> list[int]:
    indices: list[int] = []
    for index in range(1, len(fast)):
        previous_fast = fast[index - 1]
        previous_slow = slow[index - 1]
        current_fast = fast[index]
        current_slow = slow[index]
        if np.isnan([previous_fast, previous_slow, current_fast, current_slow]).any():
            continue
        crossed = (
            previous_fast <= previous_slow and current_fast > current_slow
            if bullish
            else previous_fast >= previous_slow and current_fast < current_slow
        )
        if crossed:
            indices.append(index)
    return indices


def _recent_trigger(
    df: pd.DataFrame,
    *,
    code: SignalTriggerCode,
    age: int | None,
    window: int,
) -> SignalTrigger | None:
    if age is None or age >= window:
        return None
    return SignalTrigger(
        code=code,
        occurred_at=str(df.iloc[-1 - age]["date"]),
        age_bars=age,
    )


def _reversal_triggers(
    df: pd.DataFrame,
    *,
    ema9: np.ndarray,
    ema26: np.ndarray,
    direction: np.ndarray,
    bullish: bool,
    window: int,
) -> list[SignalTrigger]:
    target = 1 if bullish else -1
    direction_code: SignalTriggerCode = (
        "supertrend_bullish_reversal" if bullish else "supertrend_bearish_reversal"
    )
    ema_code: SignalTriggerCode = "ema_bullish_crossover" if bullish else "ema_bearish_crossover"
    direction_indices = _supertrend_flip_indices(direction, target=target)
    ema_indices = _ema_cross_indices(ema9, ema26, bullish=bullish)
    direction_age = len(direction) - 1 - direction_indices[-1] if direction_indices else None
    ema_age = len(ema9) - 1 - ema_indices[-1] if ema_indices else None
    candidates = (
        _recent_trigger(
            df,
            code=direction_code,
            age=direction_age,
            window=window,
        ),
        _recent_trigger(
            df,
            code=ema_code,
            age=ema_age,
            window=window,
        ),
    )
    return [trigger for trigger in candidates if trigger is not None]


def _trigger_reason(trigger: SignalTrigger) -> str:
    labels: dict[SignalTriggerCode, str] = {
        "supertrend_bullish_reversal": "Supertrend 由空翻多",
        "ema_bullish_crossover": "EMA9 上穿 EMA26",
        "supertrend_bearish_reversal": "Supertrend 由多翻空",
        "ema_bearish_crossover": "EMA9 下穿 EMA26",
    }
    age = "触发当日" if trigger.age_bars == 0 else f"{trigger.age_bars} 根日线前"
    return f"{labels[trigger.code]}（{trigger.occurred_at}，{age}）"


def _active_bearish_triggers(
    triggers: list[SignalTrigger],
    *,
    ema_bearish: bool,
    price_below_ema26: bool,
    supertrend_bearish: bool,
) -> list[SignalTrigger]:
    return [
        trigger
        for trigger in triggers
        if (trigger.code == "supertrend_bearish_reversal" and supertrend_bearish)
        or (trigger.code == "ema_bearish_crossover" and ema_bearish and price_below_ema26)
    ]


def _single_event_confirmation(triggers: list[SignalTrigger]) -> SignalConfirmation:
    latest = min(triggers, key=lambda trigger: trigger.age_bars)
    return SignalConfirmation(
        confirmed_at=latest.occurred_at,
        age_bars=latest.age_bars,
    )


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

    bullish_structure = ema9 > ema26 and direction_array[-1] > 0
    bearish_structure = ema9 < ema26 and direction_array[-1] < 0
    bullish_setup = _reversal_triggers(
        df,
        ema9=ema9_array,
        ema26=ema26_array,
        direction=direction_array,
        bullish=True,
        window=_BUY_TRIGGER_WINDOW,
    )
    bullish_triggers = [
        trigger for trigger in bullish_setup if trigger.code == "supertrend_bullish_reversal"
    ]
    bearish_setup = _reversal_triggers(
        df,
        ema9=ema9_array,
        ema26=ema26_array,
        direction=direction_array,
        bullish=False,
        window=_SELL_TRIGGER_WINDOW,
    )
    sell_triggers = _active_bearish_triggers(
        bearish_setup,
        ema_bearish=ema9 < ema26,
        price_below_ema26=current_close < ema26,
        supertrend_bearish=direction_array[-1] < 0,
    )
    buy_rejections: list[str] = []
    if rsi >= _ENTRY_RSI_OVERHEATED:
        buy_rejections.append(f"RSI14={rsi:.2f} 已过热")
    if current_close < ema26:
        buy_rejections.append("收盘价低于 EMA26")

    reasons: list[str] = []
    confirmation: SignalConfirmation | None = None
    if sell_triggers:
        state: AssessmentState = "sell"
        triggers = sell_triggers
        confirmation = _single_event_confirmation(triggers)
        reasons.append(
            f"空头反转触发风险预警（{confirmation.confirmed_at}，"
            f"信号 age_bars={confirmation.age_bars}）"
        )
        reasons.extend(_trigger_reason(trigger) for trigger in triggers)
    elif bullish_triggers and direction_array[-1] > 0 and not buy_rejections:
        state = "buy"
        triggers = bullish_triggers
        confirmation = _single_event_confirmation(triggers)
        reasons.append(
            f"Supertrend 完成多头反转（{confirmation.confirmed_at}，"
            f"信号 age_bars={confirmation.age_bars}）"
        )
        reasons.extend(_trigger_reason(trigger) for trigger in triggers)
    elif not bullish_structure and not bearish_structure:
        state = "watch"
        triggers = bullish_setup or bearish_setup
        reasons.append("EMA9/EMA26 与 Supertrend 方向尚未形成一致反转")
    elif bullish_triggers and direction_array[-1] > 0:
        state = "watch"
        triggers = bullish_triggers
        confirmation = _single_event_confirmation(triggers)
        reasons.append(f"多头反转已确认但当前不宜追入（{confirmation.confirmed_at}）")
        reasons.extend(_trigger_reason(trigger) for trigger in triggers)
        reasons.extend(buy_rejections)
    elif bullish_triggers or bearish_setup:
        state = "watch"
        triggers = bullish_triggers or bearish_setup
        reasons.extend(_trigger_reason(trigger) for trigger in triggers)
        reasons.append("近期反转事件已出现，但当前趋势结构尚未满足信号条件")
    elif bullish_structure and current_close > ema9:
        state = "hold"
        triggers = []
        reasons.append("多头趋势结构保持且无新反转事件，处于持有观察")
    elif bullish_structure:
        state = "watch"
        triggers = []
        reasons.append("多头结构保持但收盘价跌破 EMA9，趋势转弱观察")
    else:
        state = "ignored"
        triggers = []
        reasons.append("当前趋势未在有效确认日线窗口内发生反转")

    if turnover_ratio is not None and turnover_ratio < 0.8:
        reasons.append(f"5 日成交额量比 {turnover_ratio:.2f}，量能偏弱")

    quality_direction: TrendDirection
    if state in ("buy", "hold"):
        quality_direction = "bullish"
    elif state == "sell":
        quality_direction = "bearish"
    else:
        quality_direction = "neutral"

    risk = None
    if state in ("buy", "hold"):
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
        confirmation=confirmation,
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
