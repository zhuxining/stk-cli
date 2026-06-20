"""Trend-first signal scoring service."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd
import talib

from stk.errors import IndicatorError
from stk.models.score import (
    ContextBias,
    ContextFactor,
    Decision,
    DecisionSignal,
    EmaCross,
    FactorState,
    MetricValue,
    PrimarySignal,
    RiskLevel,
    RiskProfile,
    ScoreResult,
    SignalContext,
    SignalPattern,
    SignalStatus,
    SignalStrength,
    SupertrendFlip,
    TrendDirection,
    TrendSignal,
)
from stk.services.history import candles_to_df, get_history
from stk.services.indicator import _calc_supertrend_arrays
from stk.utils.trading_session import is_unclosed_daily_bar

_EMA_FAST = 9
_EMA_SLOW = 26
_RESONANCE_WINDOW = 2
_MIN_HISTORY = 30
_MIN_ENTRY_RISK_REWARD = 1.2
_STRONG_RISK_REWARD = 1.8
_STRENGTH_RANK: dict[SignalStrength | None, int] = {"推荐": 0, "预警": 1, None: 2}


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


def _safe_last(series: pd.Series | np.ndarray) -> float | None:
    """Get last non-NaN value from a series."""
    val = series.iloc[-1] if isinstance(series, pd.Series) else series[-1]
    return None if np.isnan(val) else round(float(val), 4)


def _metric(value: float | int | None, *, digits: int = 4) -> float | None:
    if value is None or np.isnan(value):
        return None
    return round(float(value), digits)


def _clean_metrics(metrics: dict[str, MetricValue]) -> dict[str, MetricValue]:
    return {key: value for key, value in metrics.items() if value is not None}


def _rsi_zone(rsi: float | None) -> str | None:
    if rsi is None:
        return None
    if rsi < 30:
        return "oversold"
    if rsi < 40:
        return "weak"
    if rsi <= 60:
        return "neutral"
    if rsi <= 70:
        return "strong"
    return "overbought"


def _mfi_zone(mfi: float | None) -> str | None:
    if mfi is None:
        return None
    if mfi < 20:
        return "oversold"
    if mfi < 40:
        return "weak"
    if mfi <= 60:
        return "neutral"
    if mfi <= 80:
        return "strong"
    return "overbought"


def _direction_label(direction: TrendDirection) -> str:
    match direction:
        case "bullish":
            return "多头"
        case "bearish":
            return "空头"
        case _:
            return "中性"


def _format_age(age: int) -> str:
    return "当前K线" if age == 0 else f"{age}根K线前"


def _min_age(ages: Iterable[int | None]) -> int | None:
    valid = [age for age in ages if age is not None]
    return min(valid) if valid else None


def _last_ema_cross_age(ema_fast: np.ndarray, ema_slow: np.ndarray, *, golden: bool) -> int | None:
    """Return bars since the latest EMA cross, or None."""
    last_index: int | None = None
    for i in range(1, len(ema_fast)):
        if np.isnan(ema_fast[i - 1]) or np.isnan(ema_slow[i - 1]):
            continue
        if np.isnan(ema_fast[i]) or np.isnan(ema_slow[i]):
            continue

        golden_cross = ema_fast[i - 1] <= ema_slow[i - 1] and ema_fast[i] > ema_slow[i]
        death_cross = ema_fast[i - 1] >= ema_slow[i - 1] and ema_fast[i] < ema_slow[i]
        if (golden and golden_cross) or (not golden and death_cross):
            last_index = i

    return None if last_index is None else len(ema_fast) - 1 - last_index


def _last_supertrend_flip_age(direction: np.ndarray, *, target: int) -> int | None:
    """Return bars since the latest Supertrend flip into target direction."""
    last_index: int | None = None
    for i in range(1, len(direction)):
        if direction[i - 1] == 0 or direction[i] == 0:
            continue
        if direction[i - 1] != target and direction[i] == target:
            last_index = i
    return None if last_index is None else len(direction) - 1 - last_index


def _event_date(df: pd.DataFrame, age: int | None) -> str | None:
    if age is None:
        return None
    return str(df.iloc[len(df) - 1 - age]["date"])


def _build_reasons(
    *,
    ema9: float,
    ema26: float,
    st_direction: TrendDirection,
    golden_age: int | None,
    death_age: int | None,
    bull_flip_age: int | None,
    bear_flip_age: int | None,
) -> list[str]:
    reasons: list[str] = []

    if ema9 > ema26:
        reasons.append(f"EMA9 位于 EMA26 上方 ({ema9:.2f}>{ema26:.2f})")
    elif ema9 < ema26:
        reasons.append(f"EMA9 位于 EMA26 下方 ({ema9:.2f}<{ema26:.2f})")
    else:
        reasons.append(f"EMA9 与 EMA26 粘合 ({ema9:.2f})")

    reasons.append(f"Supertrend 当前为{_direction_label(st_direction)}")

    events = [
        (golden_age, "EMA 金叉"),
        (death_age, "EMA 死叉"),
        (bull_flip_age, "Supertrend 多头翻转"),
        (bear_flip_age, "Supertrend 空头翻转"),
    ]
    for age, label in events:
        if age is not None and age <= _RESONANCE_WINDOW:
            reasons.append(f"{label}发生在{_format_age(age)}")

    return reasons


def _check_low_volume_cross(df: pd.DataFrame, reasons: list[str]) -> None:
    """Warn if a fresh golden cross is accompanied by low volume (likely false breakout)."""
    turnover = df["turnover"].astype(float)
    if len(turnover) < 6:
        return
    avg_vol = turnover.iloc[-6:-1].mean()
    cur_vol = turnover.iloc[-1]
    if avg_vol <= 0:
        return
    vol_ratio = cur_vol / avg_vol
    if vol_ratio < 0.8:
        reasons.append(f"缩量金叉 (量比 {vol_ratio:.1f})，突破有效性存疑")


def _build_trend_signal(
    df: pd.DataFrame,
    *,
    ema9_arr: np.ndarray,
    ema26_arr: np.ndarray,
    supertrend_arr: np.ndarray,
    st_direction_arr: np.ndarray,
    ema60_arr: np.ndarray | None = None,
) -> TrendSignal:
    ema9 = _safe_last(ema9_arr)
    ema26 = _safe_last(ema26_arr)
    supertrend = _safe_last(supertrend_arr)
    current_close = round(float(df["close"].iloc[-1]), 4)

    if ema9 is None or ema26 is None or supertrend is None:
        return TrendSignal(
            strength=None,
            direction="neutral",
            ema9=ema9,
            ema26=ema26,
            supertrend=supertrend,
            supertrend_direction="neutral",
            reasons=["EMA 或 Supertrend 尚未形成有效值"],
        )

    current_st_direction = st_direction_arr[-1]
    st_direction: TrendDirection
    if current_st_direction > 0:
        st_direction = "bullish"
    elif current_st_direction < 0:
        st_direction = "bearish"
    else:
        st_direction = "neutral"

    golden_age = _last_ema_cross_age(ema9_arr, ema26_arr, golden=True)
    death_age = _last_ema_cross_age(ema9_arr, ema26_arr, golden=False)
    bull_flip_age = _last_supertrend_flip_age(st_direction_arr, target=1)
    bear_flip_age = _last_supertrend_flip_age(st_direction_arr, target=-1)
    bull_event_age = _min_age([golden_age, bull_flip_age])
    bear_event_age = _min_age([death_age, bear_flip_age])

    ema_bullish = ema9 > ema26
    ema_bearish = ema9 < ema26
    st_bullish = st_direction == "bullish"
    st_bearish = st_direction == "bearish"

    reasons = _build_reasons(
        ema9=ema9,
        ema26=ema26,
        st_direction=st_direction,
        golden_age=golden_age,
        death_age=death_age,
        bull_flip_age=bull_flip_age,
        bear_flip_age=bear_flip_age,
    )

    strength: SignalStrength | None = None
    direction: TrendDirection = "neutral"
    signal_age: int | None = None
    ema_cross: EmaCross | None = None
    st_flip: SupertrendFlip | None = None

    price_above_ema9 = current_close > ema9
    price_below_ema9 = current_close < ema9

    if ema_bullish and st_bullish and bull_event_age is not None:
        direction = "bullish"
        signal_age = bull_event_age
        if not price_above_ema9:
            signal_age = None
            reasons.append("收盘价未站上 EMA9，多头趋势等待确认")
        elif signal_age <= _RESONANCE_WINDOW:
            strength = "推荐"
        else:
            signal_age = None
            reasons.append("多头排列存在，但最近3根K线内没有新触发")

        if golden_age is not None and golden_age == signal_age:
            ema_cross = "golden"
        if bull_flip_age is not None and bull_flip_age == signal_age:
            st_flip = "bullish"

    elif ema_bearish and st_bearish and bear_event_age is not None:
        direction = "bearish"
        signal_age = bear_event_age
        if not price_below_ema9:
            signal_age = None
            reasons.append("收盘价未跌回 EMA9 下方，空头趋势等待确认")
        elif signal_age <= _RESONANCE_WINDOW:
            strength = "预警"
        else:
            signal_age = None
            reasons.append("空头排列存在，但最近3根K线内没有新触发")

        if death_age is not None and death_age == signal_age:
            ema_cross = "death"
        if bear_flip_age is not None and bear_flip_age == signal_age:
            st_flip = "bearish"

    elif ema_bullish and st_bullish:
        direction = "bullish"
        if price_above_ema9:
            reasons.append("多头排列存在，但最近3根K线内没有新触发")
        else:
            reasons.append("多头排列存在，但收盘价未站上 EMA9")
    elif ema_bearish and st_bearish:
        direction = "bearish"
        if price_below_ema9:
            reasons.append("空头排列存在，但最近3根K线内没有新触发")
        else:
            reasons.append("空头排列存在，但收盘价未跌回 EMA9 下方")
    else:
        reasons.append("EMA 与 Supertrend 方向不一致，等待收盘确认")

    if ema_cross == "golden" and strength is not None:
        _check_low_volume_cross(df, reasons)

    if ema_cross == "golden" and ema60_arr is not None and strength is not None:
        ema60 = _safe_last(ema60_arr)
        if ema60 is not None and current_close < ema60:
            reasons.append(f"价格仍在 EMA60 ({ema60:.2f}) 下方，长周期趋势偏空")

    return TrendSignal(
        strength=strength,
        direction=direction,
        signal_date=_event_date(df, signal_age),
        bars_since_signal=signal_age,
        ema9=ema9,
        ema26=ema26,
        supertrend=supertrend,
        supertrend_direction=st_direction,
        ema_cross=ema_cross,
        supertrend_flip=st_flip,
        reasons=reasons,
    )


def _signal_status(age: int | None) -> SignalStatus:
    if age is None:
        return "stale"
    if age <= 1:
        return "new"
    if age <= _RESONANCE_WINDOW:
        return "active"
    return "stale"


def _decision_signal(trend_signal: TrendSignal) -> DecisionSignal:
    if trend_signal.strength is None:
        return "观察"
    match trend_signal.pattern, trend_signal.direction:
        case "趋势共振", "bullish":
            return "趋势买入"
        case "趋势共振", "bearish":
            return "趋势退出"
        case "超卖修复", "bullish":
            return "超卖修复"
    return "观察"


def _build_decision(trend_signal: TrendSignal) -> Decision:
    return Decision(
        signal=_decision_signal(trend_signal),
        strength=trend_signal.strength,
        signal_status=_signal_status(trend_signal.bars_since_signal),
        signal_date=trend_signal.signal_date,
        bars_since_signal=trend_signal.bars_since_signal,
    )


def _build_primary_signal(trend_signal: TrendSignal, *, adx: float | None) -> PrimarySignal:
    reasons = list(trend_signal.reasons)
    if adx is not None:
        if adx < 20:
            reasons.append(f"ADX {adx:.1f}，趋势强度偏弱")
        elif adx >= 25:
            reasons.append(f"ADX {adx:.1f}，趋势强度较强")

    return PrimarySignal(
        ema_cross=trend_signal.ema_cross,
        ema9=trend_signal.ema9,
        ema26=trend_signal.ema26,
        supertrend=trend_signal.supertrend,
        supertrend_direction=trend_signal.supertrend_direction,
        adx=adx,
        reasons=reasons,
    )


def _factor_by_name(context: SignalContext, name: str) -> ContextFactor | None:
    return next((factor for factor in context.factors if factor.name == name), None)


def _metric_number(factor: ContextFactor | None, name: str) -> float | None:
    if factor is None:
        return None
    value = factor.metrics.get(name)
    return float(value) if isinstance(value, int | float) else None


def _setup_signal(
    df: pd.DataFrame,
    base_signal: TrendSignal,
    *,
    pattern: SignalPattern,
    direction: TrendDirection,
    strength: SignalStrength,
    reasons: list[str],
) -> TrendSignal:
    return TrendSignal(
        strength=strength,
        direction=direction,
        pattern=pattern,
        signal_date=_event_date(df, 0),
        bars_since_signal=0,
        ema9=base_signal.ema9,
        ema26=base_signal.ema26,
        supertrend=base_signal.supertrend,
        supertrend_direction=base_signal.supertrend_direction,
        reasons=reasons,
    )


def _build_oversold_repair_signal(
    df: pd.DataFrame,
    base_signal: TrendSignal,
    *,
    context: SignalContext,
    close_arr: np.ndarray,
    ema9_arr: np.ndarray,
) -> TrendSignal | None:
    if context.overall_bias in ("conflicting", "mixed"):
        return None

    current_close = round(float(close_arr[-1]), 4)
    ema5 = _metric_number(_factor_by_name(context, "ema_trend"), "ema5")

    # Condition 1: RSI ≤ 30 (true oversold)
    momentum = _factor_by_name(context, "momentum")
    rsi = _metric_number(momentum, "rsi14")
    if rsi is None or rsi > 30:
        return None

    # Condition 2: MACD柱转正 (momentum turning up)
    macd = _factor_by_name(context, "macd")
    macd_hist = _metric_number(macd, "hist")
    if macd_hist is None or macd_hist <= 0:
        return None

    # Condition 3: 站上EMA5 (short-term price stabilization)
    if ema5 is None or current_close <= ema5:
        return None

    reasons = [
        f"超卖修复：RSI {rsi} ≤ 30，MACD 柱转正 ({macd_hist:.4f})",
        f"收盘价 {current_close} 站上 EMA5 {ema5}",
    ]
    return _setup_signal(
        df,
        base_signal,
        pattern="超卖修复",
        direction="bullish",
        strength="推荐",
        reasons=reasons,
    )


def _with_strength(
    signal: TrendSignal,
    strength: SignalStrength | None,
    *,
    reason: str | None = None,
) -> TrendSignal:
    reasons = [*signal.reasons, reason] if reason else signal.reasons
    return signal.model_copy(update={"strength": strength, "reasons": reasons})


def _quality_adjusted_signal(
    signal: TrendSignal,
    *,
    context: SignalContext,
    atr: float | None,
    current_price: float,
    risk_reward_ratio: float | None,
) -> TrendSignal:
    if signal.strength is None:
        return signal

    age = signal.bars_since_signal
    if age is None or age > _RESONANCE_WINDOW:
        return _with_strength(signal, None, reason="触发已过有效窗口")

    if context.overall_bias == "conflicting":
        return _with_strength(signal, None, reason="辅助因子明显冲突，降为观察")

    if context.overall_bias == "mixed" and age is not None and age >= _RESONANCE_WINDOW:
        return _with_strength(signal, None, reason="信号陈旧且辅助因子态度不明确，降为观察")

    if signal.direction == "bullish" and (
        risk_reward_ratio is None or risk_reward_ratio < _MIN_ENTRY_RISK_REWARD
    ):
        return _with_strength(signal, None, reason="风险收益比不足，降为观察")

    return signal


def _select_signal(candidates: list[TrendSignal]) -> TrendSignal:
    return min(
        candidates,
        key=lambda signal: (
            _STRENGTH_RANK[signal.strength],
            999 if signal.bars_since_signal is None else signal.bars_since_signal,
        ),
    )


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
    if direction == "bearish":
        if bearish:
            return "confirming"
        if bullish:
            return "conflicting"
    return "neutral"


def _calc_momentum_factor(
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
    *,
    direction: TrendDirection,
) -> ContextFactor:
    rsi = talib.RSI(close.to_numpy(), timeperiod=14)
    rsi_now = _safe_last(rsi)

    k, d = talib.STOCH(
        high.to_numpy(),
        low.to_numpy(),
        close.to_numpy(),
        fastk_period=9,
        slowk_period=3,
        slowd_period=3,
    )
    j = 3 * k - 2 * d
    k_now, d_now, j_now = _safe_last(k), _safe_last(d), _safe_last(j)

    oversold = (rsi_now is not None and rsi_now < 30) or (j_now is not None and j_now < 20)
    overbought = (rsi_now is not None and rsi_now > 70) or (j_now is not None and j_now > 80)
    if oversold:
        state: FactorState = "opportunity"
    elif overbought:
        state = "risk"
    else:
        bullish = k_now is not None and d_now is not None and k_now > d_now
        bearish = k_now is not None and d_now is not None and k_now < d_now
        state = _factor_state_for_direction(
            bullish=bullish,
            bearish=bearish,
            direction=direction,
        )

    kdj_bias = None
    if k_now is not None and d_now is not None:
        kdj_bias = "bullish" if k_now > d_now else "bearish" if k_now < d_now else "neutral"
    metrics = _clean_metrics({
        "rsi14": rsi_now,
        "rsi_zone": _rsi_zone(rsi_now),
        "k": k_now,
        "d": d_now,
        "j": j_now,
        "kdj_bias": kdj_bias,
    })
    return ContextFactor(
        name="momentum",
        state=state,
        metrics=metrics,
    )


def _calc_macd_factor(
    close_arr: np.ndarray,
    *,
    direction: TrendDirection,
) -> tuple[ContextFactor, np.ndarray]:
    macd, macd_signal, macd_hist = talib.MACD(
        close_arr,
        fastperiod=12,
        slowperiod=26,
        signalperiod=9,
    )
    macd_now = _safe_last(macd)
    signal_now = _safe_last(macd_signal)
    hist_now = _safe_last(macd_hist)

    bullish = False
    bearish = False
    if macd_now is not None and signal_now is not None:
        bullish = macd_now > signal_now and hist_now is not None and hist_now > 0
        bearish = macd_now < signal_now and hist_now is not None and hist_now < 0

    state = _factor_state_for_direction(bullish=bullish, bearish=bearish, direction=direction)
    macd_bias = "bullish" if bullish else "bearish" if bearish else "neutral"
    metrics = _clean_metrics({
        "dif": macd_now,
        "dea": signal_now,
        "hist": hist_now,
        "bias": macd_bias,
    })
    return (
        ContextFactor(
            name="macd",
            state=state,
            metrics=metrics,
        ),
        macd_hist,
    )


def _calc_boll_factor(
    close_arr: np.ndarray,
    current_price: float,
    *,
    direction: TrendDirection,
) -> tuple[ContextFactor, list[str]]:
    upper, middle, lower = talib.BBANDS(close_arr, timeperiod=20, nbdevup=2, nbdevdn=2)
    upper_now = _safe_last(upper)
    middle_now = _safe_last(middle)
    lower_now = _safe_last(lower)

    if upper_now is None or middle_now is None or lower_now is None:
        return ContextFactor(name="boll", state="none"), []

    bandwidth = upper_now - lower_now
    position_pct = ((current_price - lower_now) / bandwidth * 100) if bandwidth > 0 else 50
    bw_pct = (bandwidth / middle_now * 100) if middle_now > 0 else 999

    warnings: list[str] = []
    if bw_pct < 5:
        warnings.append(f"布林收窄 (带宽{bw_pct:.1f}%)")

    if position_pct < 10:
        state: FactorState = "opportunity"
    elif position_pct >= 95:
        state = "risk"
    else:
        bullish = position_pct >= 50
        bearish = position_pct < 50
        state = _factor_state_for_direction(
            bullish=bullish,
            bearish=bearish,
            direction=direction,
        )

    metrics = _clean_metrics({
        "upper": upper_now,
        "middle": middle_now,
        "lower": lower_now,
        "position_pct": round(position_pct, 1),
        "bandwidth_pct": round(bw_pct, 1),
    })
    return (
        ContextFactor(
            name="boll",
            state=state,
            metrics=metrics,
        ),
        warnings,
    )


def _calc_volume_price_factor(
    df: pd.DataFrame,
    close: pd.Series,
    *,
    direction: TrendDirection,
) -> ContextFactor:
    turnover = df["turnover"].astype(float) if "turnover" in df.columns else None
    if turnover is None or len(turnover) < 6:
        return ContextFactor(name="volume_price", state="none")

    avg_vol = turnover.iloc[-6:-1].mean()
    cur_vol = turnover.iloc[-1]
    vol_ratio = cur_vol / avg_vol if avg_vol > 0 else 1
    prev_close = float(close.iloc[-2])
    price_change = (float(close.iloc[-1]) - prev_close) / prev_close * 100 if prev_close > 0 else 0

    bullish = vol_ratio > 1.5 and price_change > 1
    bearish = vol_ratio > 1.5 and price_change < -1
    if vol_ratio > 2.0 and price_change < -3:
        state: FactorState = "risk"
    elif bullish:
        state = _factor_state_for_direction(bullish=True, bearish=False, direction=direction)
    elif bearish:
        state = _factor_state_for_direction(bullish=False, bearish=True, direction=direction)
    else:
        state = "neutral"

    metrics: dict[str, MetricValue] = {
        "volume_ratio_5d": round(vol_ratio, 2),
        "price_change_pct": round(price_change, 2),
    }
    return ContextFactor(
        name="volume_price",
        state=state,
        metrics=metrics,
    )


def _calc_legacy_ema_factor(
    close_arr: np.ndarray,
    current_price: float,
    *,
    direction: TrendDirection,
) -> ContextFactor:
    ema5 = talib.EMA(close_arr, timeperiod=5)
    ema10 = talib.EMA(close_arr, timeperiod=10)
    ema20 = talib.EMA(close_arr, timeperiod=20)
    e5, e10, e20 = _safe_last(ema5), _safe_last(ema10), _safe_last(ema20)
    if e5 is None or e10 is None or e20 is None:
        return ContextFactor(name="ema_trend", state="none")

    bullish = e5 > e10 > e20 and current_price > e5
    bearish = e5 < e10 < e20 and current_price < e5
    if bullish:
        arrangement = "bullish"
    elif bearish:
        arrangement = "bearish"
    else:
        arrangement = "none"

    state = _factor_state_for_direction(bullish=bullish, bearish=bearish, direction=direction)
    metrics = _clean_metrics({
        "ema5": e5,
        "ema10": e10,
        "ema20": e20,
        "arrangement": arrangement,
    })
    return ContextFactor(
        name="ema_trend",
        state=state,
        metrics=metrics,
    )


def _calc_money_flow_factor(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    *,
    direction: TrendDirection,
) -> ContextFactor:
    mfi = talib.MFI(
        high.to_numpy().astype(float),
        low.to_numpy().astype(float),
        close.to_numpy().astype(float),
        volume.to_numpy().astype(float),
        timeperiod=14,
    )
    mfi_now = _safe_last(mfi)
    if mfi_now is None:
        return ContextFactor(name="money_flow", state="none")

    metrics = _clean_metrics({"mfi14": mfi_now, "mfi_zone": _mfi_zone(mfi_now)})
    if mfi_now < 20:
        state: FactorState = "opportunity"
    elif mfi_now > 80:
        state = "risk"
    elif direction == "bullish":
        state = "confirming" if mfi_now > 60 else "conflicting" if mfi_now < 40 else "neutral"
    elif direction == "bearish":
        state = "confirming" if mfi_now < 40 else "conflicting" if mfi_now > 60 else "neutral"
    elif mfi_now < 40:
        state = "opportunity"
    elif mfi_now <= 60:
        state = "neutral"
    else:
        state = "risk"
    return ContextFactor(
        name="money_flow",
        state=state,
        metrics=metrics,
    )


def _calc_divergence_factor(
    close: pd.Series,
    macd_hist: np.ndarray,
    *,
    lookback: int = 20,
) -> ContextFactor:
    if len(close) < lookback + 1 or len(macd_hist) < lookback + 1:
        return ContextFactor(name="divergence", state="none")

    window_close = close.iloc[-(lookback + 1) : -1]
    window_hist = macd_hist[-(lookback + 1) : -1]
    cur_close = float(close.iloc[-1])
    cur_hist = float(macd_hist[-1]) if not np.isnan(macd_hist[-1]) else None
    if cur_hist is None:
        return ContextFactor(name="divergence", state="none")

    min_idx = int(window_close.to_numpy().argmin())
    max_idx = int(window_close.to_numpy().argmax())
    prev_low = float(window_close.iloc[min_idx])
    prev_high = float(window_close.iloc[max_idx])
    hist_at_low = float(window_hist[min_idx]) if not np.isnan(window_hist[min_idx]) else None
    hist_at_high = float(window_hist[max_idx]) if not np.isnan(window_hist[max_idx]) else None

    def _divergence_metrics(
        divergence_type: str,
        *,
        reference_price: float | None = None,
        reference_hist: float | None = None,
    ) -> dict[str, MetricValue]:
        price_distance_pct = (
            (cur_close - reference_price) / reference_price * 100
            if reference_price and reference_price > 0
            else None
        )
        hist_delta = cur_hist - reference_hist if reference_hist is not None else None
        return _clean_metrics({
            "type": divergence_type,
            "lookback": lookback,
            "current_close": round(cur_close, 4),
            "reference_price": _metric(reference_price),
            "current_hist": _metric(cur_hist),
            "reference_hist": _metric(reference_hist),
            "price_distance_pct": _metric(price_distance_pct, digits=2),
            "hist_delta": _metric(hist_delta),
        })

    if hist_at_low is not None and cur_close <= prev_low * 1.02 and cur_hist > hist_at_low:
        return ContextFactor(
            name="divergence",
            state="opportunity",
            metrics=_divergence_metrics(
                "macd_bullish",
                reference_price=prev_low,
                reference_hist=hist_at_low,
            ),
        )
    if hist_at_high is not None and cur_close >= prev_high * 0.98 and cur_hist < hist_at_high:
        return ContextFactor(
            name="divergence",
            state="risk",
            metrics=_divergence_metrics(
                "macd_bearish",
                reference_price=prev_high,
                reference_hist=hist_at_high,
            ),
        )
    return ContextFactor(
        name="divergence",
        state="none",
        metrics=_divergence_metrics("none"),
    )


def _overall_bias(factors: list[ContextFactor]) -> ContextBias:
    confirming = sum(f.state == "confirming" for f in factors)
    conflicting = sum(f.state == "conflicting" for f in factors)
    risky = sum(f.state == "risk" for f in factors)

    if conflicting >= 2 or conflicting > confirming:
        return "conflicting"
    if risky >= 2 or (risky > 0 and confirming < 2):
        return "risky"
    if confirming >= 2 and conflicting == 0:
        return "supportive"
    return "mixed"


def _build_context(
    df: pd.DataFrame,
    *,
    direction: TrendDirection,
    close_arr: np.ndarray,
    current_price: float,
) -> SignalContext:
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    macd_factor, macd_hist = _calc_macd_factor(close_arr, direction=direction)
    boll_factor, warnings = _calc_boll_factor(
        close_arr,
        current_price,
        direction=direction,
    )
    factors = [
        _calc_momentum_factor(close, high, low, direction=direction),
        macd_factor,
        boll_factor,
        _calc_volume_price_factor(df, close, direction=direction),
        _calc_legacy_ema_factor(close_arr, current_price, direction=direction),
        _calc_money_flow_factor(high, low, close, volume, direction=direction),
        _calc_divergence_factor(close, macd_hist),
    ]
    return SignalContext(
        overall_bias=_overall_bias(factors),
        factors=factors,
        warnings=warnings,
    )


def _risk_level(risk_reward_ratio: float | None) -> RiskLevel:
    if risk_reward_ratio is None:
        return "medium"
    if risk_reward_ratio >= _STRONG_RISK_REWARD:
        return "low"
    if risk_reward_ratio >= _MIN_ENTRY_RISK_REWARD:
        return "medium"
    return "high"


@dataclass
class _RiskPoints:
    """Internal risk calculation result."""

    stop_loss: float
    target_1: float
    target_2: float
    trailing_stop: float | None
    rr_ratio: float | None

    @property
    def take_profit(self) -> float:
        """Backward compatibility alias for target_2."""
        return self.target_2


def _build_risk_profile(
    *,
    atr: float | None,
    rp: _RiskPoints | None = None,
) -> RiskProfile:
    if rp is None:
        return RiskProfile(atr=atr, risk_level=_risk_level(None))
    return RiskProfile(
        atr=atr,
        stop_loss=rp.stop_loss,
        take_profit=rp.take_profit,
        target_1=rp.target_1,
        target_2=rp.target_2,
        trailing_stop=rp.trailing_stop,
        risk_reward_ratio=rp.rr_ratio,
        risk_level=_risk_level(rp.rr_ratio),
    )


def _risk_points(
    *,
    current_price: float,
    atr: float,
    trend_signal: TrendSignal,
) -> _RiskPoints:
    trailing_stop = (
        round(trend_signal.supertrend, 4) if trend_signal.supertrend is not None else None
    )
    if trend_signal.direction == "bearish":
        fallback_stop = current_price + atr * 2.0
        stop_loss = fallback_stop
        if (
            trend_signal.supertrend is not None
            and trend_signal.supertrend_direction == "bearish"
            and trend_signal.supertrend > current_price
        ):
            stop_loss = min(trend_signal.supertrend, fallback_stop)
        target_1 = max(current_price - atr * 2.0, 0.0)
        target_2 = max(current_price - atr * 3.0, 0.0)
        risk = stop_loss - current_price
        reward = current_price - target_2
    else:
        fallback_stop = current_price - atr * 2.0
        stop_loss = fallback_stop
        if (
            trend_signal.supertrend is not None
            and trend_signal.supertrend_direction == "bullish"
            and trend_signal.supertrend < current_price
        ):
            stop_loss = max(trend_signal.supertrend, fallback_stop)
        target_1 = current_price + atr * 2.0
        target_2 = current_price + atr * 3.0
        risk = current_price - stop_loss
        reward = target_2 - current_price

    rr_ratio = round(reward / risk, 1) if risk > 0 else None
    return _RiskPoints(
        stop_loss=round(stop_loss, 4),
        target_1=round(target_1, 4),
        target_2=round(target_2, 4),
        trailing_stop=trailing_stop,
        rr_ratio=rr_ratio,
    )


def calc_score(symbol: str, *, count: int = 60) -> ScoreResult:
    """Calculate trend-first monitoring decision from daily closed candles."""
    candles = get_history(symbol, count=count)
    if not candles:
        raise IndicatorError(f"Insufficient history for {symbol} (need>={_MIN_HISTORY}, got 0)")

    df = _closed_daily_df(candles_to_df(candles), symbol)
    if len(df) < _MIN_HISTORY:
        raise IndicatorError(
            f"Insufficient closed daily history for {symbol} (need>={_MIN_HISTORY}, got {len(df)})"
        )
    close = df["close"].to_numpy(dtype=float)
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    current_price = float(close[-1])

    ema9_arr = talib.EMA(close, timeperiod=_EMA_FAST)
    ema26_arr = talib.EMA(close, timeperiod=_EMA_SLOW)
    ema60_arr = talib.EMA(close, timeperiod=60)
    supertrend_arr, st_direction_arr, atr_arr = _calc_supertrend_arrays(high, low, close)

    trend_signal = _build_trend_signal(
        df,
        ema9_arr=ema9_arr,
        ema26_arr=ema26_arr,
        supertrend_arr=supertrend_arr,
        st_direction_arr=st_direction_arr,
        ema60_arr=ema60_arr,
    )

    adx_series = talib.ADX(high, low, close, timeperiod=14)
    adx_last = _safe_last(adx_series)
    adx_val = round(adx_last, 1) if adx_last is not None else None

    atr_last = _safe_last(atr_arr)
    atr_val = round(atr_last, 4) if atr_last is not None and atr_last > 0 else None

    contexts: dict[TrendDirection, SignalContext] = {}

    def context_for(direction: TrendDirection) -> SignalContext:
        if direction not in contexts:
            contexts[direction] = _build_context(
                df,
                direction=direction,
                close_arr=close,
                current_price=current_price,
            )
        return contexts[direction]

    candidates = [trend_signal]
    bullish_context = context_for("bullish")
    if oversold_signal := _build_oversold_repair_signal(
        df,
        trend_signal,
        context=bullish_context,
        close_arr=close,
        ema9_arr=ema9_arr,
    ):
        candidates.append(oversold_signal)

    def _candidate_rr(signal: TrendSignal) -> float | None:
        if atr_last is None or atr_last <= 0 or signal.direction == "neutral":
            return None
        return _risk_points(
            current_price=current_price,
            atr=atr_last,
            trend_signal=signal,
        ).rr_ratio

    adjusted_candidates = [
        _quality_adjusted_signal(
            candidate,
            context=context_for(candidate.direction),
            atr=atr_last,
            current_price=current_price,
            risk_reward_ratio=_candidate_rr(candidate),
        )
        for candidate in candidates
    ]
    selected_signal = _select_signal(adjusted_candidates)

    rp = None
    if atr_last is not None and atr_last > 0:
        rp = _risk_points(
            current_price=current_price,
            atr=atr_last,
            trend_signal=selected_signal,
        )

    decision = _build_decision(selected_signal)
    primary_signal = _build_primary_signal(selected_signal, adx=adx_val)
    context = context_for(selected_signal.direction)
    risk_profile = _build_risk_profile(atr=atr_val, rp=rp)

    return ScoreResult(
        symbol=symbol,
        decision=decision,
        primary_signal=primary_signal,
        context=context,
        risk=risk_profile,
    )
