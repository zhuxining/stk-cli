"""Trend-first signal scoring service."""

from collections.abc import Iterable

import numpy as np
import pandas as pd
import talib

from stk.errors import IndicatorError
from stk.models.score import (
    ContextBias,
    ContextFactor,
    Decision,
    DecisionAction,
    EmaCross,
    FactorState,
    PrimarySignal,
    RiskLevel,
    RiskProfile,
    ScoreResult,
    SignalContext,
    SignalLevel,
    SignalStatus,
    SupertrendFlip,
    TrendDirection,
    TrendSignal,
)
from stk.services.history import candles_to_df, get_history
from stk.services.indicator import _calc_supertrend_arrays

_EMA_FAST = 9
_EMA_SLOW = 26
_RESONANCE_WINDOW = 3
_MIN_HISTORY = 30


def _safe_last(series: pd.Series | np.ndarray) -> float | None:
    """Get last non-NaN value from a series."""
    val = series.iloc[-1] if isinstance(series, pd.Series) else series[-1]
    return None if np.isnan(val) else round(float(val), 4)


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

    if golden_age is not None and golden_age <= _RESONANCE_WINDOW:
        reasons.append(f"EMA 金叉发生在{_format_age(golden_age)}")
    if death_age is not None and death_age <= _RESONANCE_WINDOW:
        reasons.append(f"EMA 死叉发生在{_format_age(death_age)}")
    if bull_flip_age is not None and bull_flip_age <= _RESONANCE_WINDOW:
        reasons.append(f"Supertrend 多头翻转发生在{_format_age(bull_flip_age)}")
    if bear_flip_age is not None and bear_flip_age <= _RESONANCE_WINDOW:
        reasons.append(f"Supertrend 空头翻转发生在{_format_age(bear_flip_age)}")

    return reasons


def _build_trend_signal(
    df: pd.DataFrame,
    *,
    ema9_arr: np.ndarray,
    ema26_arr: np.ndarray,
    supertrend_arr: np.ndarray,
    st_direction_arr: np.ndarray,
) -> TrendSignal:
    ema9 = _safe_last(ema9_arr)
    ema26 = _safe_last(ema26_arr)
    supertrend = _safe_last(supertrend_arr)

    if ema9 is None or ema26 is None or supertrend is None:
        return TrendSignal(
            level="hold",
            direction="neutral",
            confidence=25.0,
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

    level: SignalLevel = "hold"
    direction: TrendDirection = "neutral"
    confidence = 35.0
    signal_age: int | None = None
    ema_cross: EmaCross | None = None
    st_flip: SupertrendFlip | None = None

    if ema_bullish and st_bullish and bull_event_age is not None:
        direction = "bullish"
        signal_age = bull_event_age
        if signal_age <= 1:
            level = "strong_buy"
            confidence = 92.0
        elif signal_age <= _RESONANCE_WINDOW:
            level = "buy"
            confidence = 76.0
        else:
            confidence = 48.0
            reasons.append("多头排列存在，但最近3根K线内没有新触发")

        if golden_age is not None and golden_age == signal_age:
            ema_cross = "golden"
        if bull_flip_age is not None and bull_flip_age == signal_age:
            st_flip = "bullish"

    elif ema_bearish and st_bearish and bear_event_age is not None:
        direction = "bearish"
        signal_age = bear_event_age
        if signal_age <= 1:
            level = "strong_sell"
            confidence = 92.0
        elif signal_age <= _RESONANCE_WINDOW:
            level = "sell"
            confidence = 76.0
        else:
            confidence = 48.0
            reasons.append("空头排列存在，但最近3根K线内没有新触发")

        if death_age is not None and death_age == signal_age:
            ema_cross = "death"
        if bear_flip_age is not None and bear_flip_age == signal_age:
            st_flip = "bearish"

    elif ema_bullish and st_bullish:
        direction = "bullish"
        confidence = 48.0
        reasons.append("多头排列存在，但最近3根K线内没有新触发")
    elif ema_bearish and st_bearish:
        direction = "bearish"
        confidence = 48.0
        reasons.append("空头排列存在，但最近3根K线内没有新触发")
    else:
        reasons.append("EMA 与 Supertrend 方向不一致，等待收盘确认")

    return TrendSignal(
        level=level,
        direction=direction,
        confidence=confidence,
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


def _decision_action(level: SignalLevel) -> DecisionAction:
    match level:
        case "strong_buy" | "buy":
            return "focus_buy"
        case "strong_sell" | "sell":
            return "focus_sell"
        case _:
            return "watch"


def _decision_summary(level: SignalLevel) -> str:
    match level:
        case "strong_buy":
            return "EMA9/26 金叉与 Supertrend 多头强共振"
        case "buy":
            return "EMA9/26 与 Supertrend 多头确认"
        case "strong_sell":
            return "EMA9/26 死叉与 Supertrend 空头强共振"
        case "sell":
            return "EMA9/26 与 Supertrend 空头确认"
        case _:
            return "趋势信号未确认"


def _build_decision(trend_signal: TrendSignal) -> Decision:
    return Decision(
        action=_decision_action(trend_signal.level),
        level=trend_signal.level,
        direction=trend_signal.direction,
        confidence=trend_signal.confidence,
        signal_status=_signal_status(trend_signal.bars_since_signal),
        signal_date=trend_signal.signal_date,
        bars_since_signal=trend_signal.bars_since_signal,
        summary=_decision_summary(trend_signal.level),
    )


def _build_primary_signal(trend_signal: TrendSignal, *, adx: float | None) -> PrimarySignal:
    return PrimarySignal(
        ema_cross=trend_signal.ema_cross,
        ema9=trend_signal.ema9,
        ema26=trend_signal.ema26,
        supertrend=trend_signal.supertrend,
        supertrend_direction=trend_signal.supertrend_direction,
        adx=adx,
        reasons=trend_signal.reasons,
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
    rsi_ratio = 0.25

    signals: list[str] = []
    if rsi_now is not None:
        signals.append(f"RSI={rsi_now:.0f}")
        if rsi_now < 30:
            rsi_ratio = 1.0
        elif rsi_now < 40:
            rsi_ratio = 0.6
        elif rsi_now <= 60:
            rsi_ratio = 0.25
        elif rsi_now <= 70:
            rsi_ratio = 0.1
        else:
            rsi_ratio = 0.0

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
    kdj_ratio = 0.25

    if j_now is not None:
        signals.append(f"J={j_now:.0f}")
    if k_now is not None and d_now is not None:
        if j_now is not None and j_now < 20:
            kdj_ratio = 0.75
        elif j_now is not None and j_now > 80:
            kdj_ratio = 0.0
        elif k_now > d_now:
            kdj_ratio = 0.4
        else:
            kdj_ratio = 0.15

    score = round((rsi_ratio * 0.6 + kdj_ratio * 0.4) * 100, 1)

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

    return ContextFactor(name="momentum", state=state, score=score, signals=signals)


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

    signals: list[str] = []
    score = 50.0
    bullish = False
    bearish = False
    if macd_now is not None and signal_now is not None:
        signals.append(f"DIF={macd_now:.4f}")
        bullish = macd_now > signal_now and hist_now is not None and hist_now > 0
        bearish = macd_now < signal_now and hist_now is not None and hist_now < 0
        if bullish:
            score = 75.0
            signals.append("MACD多头")
        elif bearish:
            score = 25.0
            signals.append("MACD空头")

    state = _factor_state_for_direction(bullish=bullish, bearish=bearish, direction=direction)
    return ContextFactor(name="macd", state=state, score=score, signals=signals), macd_hist


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
        return ContextFactor(name="boll", state="none", score=50, signals=[]), []

    bandwidth = upper_now - lower_now
    position_pct = ((current_price - lower_now) / bandwidth * 100) if bandwidth > 0 else 50
    bw_pct = (bandwidth / middle_now * 100) if middle_now > 0 else 999

    warnings: list[str] = []
    signals = [f"BOLL位置={position_pct:.0f}%"]
    if bw_pct < 5:
        warnings.append(f"布林收窄 (带宽{bw_pct:.1f}%)")

    if position_pct < 10:
        state: FactorState = "opportunity"
        score = 100.0
    elif position_pct >= 90:
        state = "risk"
        score = 0.0
    else:
        score = round(max(0.0, min(100.0, 100 - position_pct)), 1)
        bullish = position_pct >= 50
        bearish = position_pct < 50
        state = _factor_state_for_direction(
            bullish=bullish,
            bearish=bearish,
            direction=direction,
        )

    return ContextFactor(name="boll", state=state, score=score, signals=signals), warnings


def _calc_volume_price_factor(
    df: pd.DataFrame,
    close: pd.Series,
    *,
    direction: TrendDirection,
) -> ContextFactor:
    turnover = df["turnover"].astype(float) if "turnover" in df.columns else None
    if turnover is None or len(turnover) < 6:
        return ContextFactor(name="volume_price", state="none", score=50, signals=[])

    avg_vol = turnover.iloc[-6:-1].mean()
    cur_vol = turnover.iloc[-1]
    vol_ratio = cur_vol / avg_vol if avg_vol > 0 else 1
    prev_close = float(close.iloc[-2])
    price_change = (
        (float(close.iloc[-1]) - prev_close) / prev_close * 100 if prev_close > 0 else 0
    )

    signals = [f"量比={vol_ratio:.1f}x", f"涨跌={price_change:+.1f}%"]
    bullish = vol_ratio > 1.5 and price_change > 1
    bearish = vol_ratio > 1.5 and price_change < -1
    if vol_ratio > 2.0 and price_change < -3:
        state: FactorState = "risk"
        score = 0.0
    elif bullish:
        state = _factor_state_for_direction(bullish=True, bearish=False, direction=direction)
        score = 90.0 if vol_ratio > 2.0 and price_change > 3 else 67.0
    elif bearish:
        state = _factor_state_for_direction(bullish=False, bearish=True, direction=direction)
        score = 20.0
    else:
        state = "neutral"
        score = 33.0

    return ContextFactor(name="volume_price", state=state, score=score, signals=signals)


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
        return ContextFactor(name="ema_trend", state="none", score=50, signals=[])

    bullish = e5 > e10 > e20 and current_price > e5
    bearish = e5 < e10 < e20 and current_price < e5
    if bullish:
        score = 100.0
        signals = ["EMA5>EMA10>EMA20"]
    elif bearish:
        score = 0.0
        signals = ["EMA5<EMA10<EMA20"]
    else:
        score = 50.0
        signals = ["EMA短周期未排列"]

    state = _factor_state_for_direction(bullish=bullish, bearish=bearish, direction=direction)
    return ContextFactor(name="ema_trend", state=state, score=score, signals=signals)


def _calc_money_flow_factor(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
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
        return ContextFactor(name="money_flow", state="none", score=50, signals=[])

    signals = [f"MFI={mfi_now:.0f}"]
    if mfi_now < 20:
        return ContextFactor(name="money_flow", state="opportunity", score=100, signals=signals)
    if mfi_now < 40:
        return ContextFactor(name="money_flow", state="confirming", score=67, signals=signals)
    if mfi_now <= 60:
        return ContextFactor(name="money_flow", state="neutral", score=47, signals=signals)
    if mfi_now <= 80:
        return ContextFactor(name="money_flow", state="conflicting", score=20, signals=signals)
    return ContextFactor(name="money_flow", state="risk", score=0, signals=signals)


def _calc_divergence_factor(
    close: pd.Series,
    macd_hist: np.ndarray,
    *,
    lookback: int = 20,
) -> ContextFactor:
    if len(close) < lookback + 1 or len(macd_hist) < lookback + 1:
        return ContextFactor(name="divergence", state="none", score=50, signals=[])

    window_close = close.iloc[-(lookback + 1) : -1]
    window_hist = macd_hist[-(lookback + 1) : -1]
    cur_close = float(close.iloc[-1])
    cur_hist = float(macd_hist[-1]) if not np.isnan(macd_hist[-1]) else None
    if cur_hist is None:
        return ContextFactor(name="divergence", state="none", score=50, signals=[])

    min_idx = int(window_close.to_numpy().argmin())
    max_idx = int(window_close.to_numpy().argmax())
    prev_low = float(window_close.iloc[min_idx])
    prev_high = float(window_close.iloc[max_idx])
    hist_at_low = float(window_hist[min_idx]) if not np.isnan(window_hist[min_idx]) else None
    hist_at_high = float(window_hist[max_idx]) if not np.isnan(window_hist[max_idx]) else None

    if hist_at_low is not None and cur_close <= prev_low * 1.02 and cur_hist > hist_at_low:
        return ContextFactor(
            name="divergence",
            state="opportunity",
            score=100,
            signals=["MACD底背离"],
        )
    if hist_at_high is not None and cur_close >= prev_high * 0.98 and cur_hist < hist_at_high:
        return ContextFactor(name="divergence", state="risk", score=0, signals=["MACD顶背离"])
    return ContextFactor(name="divergence", state="none", score=50, signals=["无背离"])


def _overall_bias(factors: list[ContextFactor]) -> ContextBias:
    confirming = sum(f.state == "confirming" for f in factors)
    conflicting = sum(f.state == "conflicting" for f in factors)
    risky = sum(f.state == "risk" for f in factors)
    if conflicting >= 2 or conflicting > confirming:
        return "conflicting"
    if risky >= 2:
        return "risky"
    if confirming >= 2 and conflicting == 0:
        return "supportive"
    if risky > 0:
        return "risky"
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
        _calc_money_flow_factor(high, low, close, volume),
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
    if risk_reward_ratio >= 2:
        return "low"
    if risk_reward_ratio >= 1:
        return "medium"
    return "high"


def _build_risk_profile(
    *,
    atr: float | None,
    stop_loss: float | None,
    take_profit: float | None,
    risk_reward_ratio: float | None,
) -> RiskProfile:
    return RiskProfile(
        atr=atr,
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_reward_ratio=risk_reward_ratio,
        risk_level=_risk_level(risk_reward_ratio),
    )


def calc_score(symbol: str, *, count: int = 60) -> ScoreResult:
    """Calculate trend-first signal confidence from daily closed candles."""
    candles = get_history(symbol, count=count)
    if not candles or len(candles) < _MIN_HISTORY:
        got = len(candles) if candles else 0
        raise IndicatorError(f"Insufficient history for {symbol} (need>={_MIN_HISTORY}, got {got})")

    df = candles_to_df(candles)
    close = df["close"].to_numpy(dtype=float)
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    current_price = float(close[-1])

    ema9_arr = talib.EMA(close, timeperiod=_EMA_FAST)
    ema26_arr = talib.EMA(close, timeperiod=_EMA_SLOW)
    supertrend_arr, st_direction_arr, atr_arr = _calc_supertrend_arrays(high, low, close)

    trend_signal = _build_trend_signal(
        df,
        ema9_arr=ema9_arr,
        ema26_arr=ema26_arr,
        supertrend_arr=supertrend_arr,
        st_direction_arr=st_direction_arr,
    )

    adx_series = talib.ADX(high, low, close, timeperiod=14)
    adx_last = _safe_last(adx_series)
    if adx_last is not None:
        adx_val = round(adx_last, 1)

    atr_val = None
    stop_loss = None
    take_profit = None
    rr_ratio = None

    atr_last = _safe_last(atr_arr)
    if atr_last is not None and atr_last > 0:
        atr_val = round(atr_last, 4)
        if (
            trend_signal.supertrend is not None
            and trend_signal.supertrend_direction == "bullish"
            and trend_signal.supertrend < current_price
        ):
            stop_loss = round(trend_signal.supertrend, 4)
        else:
            stop_loss = round(current_price - atr_last * 2.0, 4)

        take_profit = round(current_price + atr_last * 3.0, 4)
        risk = current_price - stop_loss
        rr_ratio = round((take_profit - current_price) / risk, 1) if risk > 0 else None

    decision = _build_decision(trend_signal)
    primary_signal = _build_primary_signal(trend_signal, adx=adx_val)
    context = _build_context(
        df,
        direction=decision.direction,
        close_arr=close,
        current_price=current_price,
    )
    risk_profile = _build_risk_profile(
        atr=atr_val,
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_reward_ratio=rr_ratio,
    )

    return ScoreResult(
        symbol=symbol,
        decision=decision,
        primary_signal=primary_signal,
        context=context,
        risk=risk_profile,
    )
