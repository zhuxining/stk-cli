"""Multi-indicator resonance scoring service."""

import numpy as np
import pandas as pd
import talib

from stk.errors import IndicatorError
from stk.models.score import ScoreDimension, ScoreResult
from stk.services.history import candles_to_df, get_history

# --- Unified weights (stock & ETF) ---
# 动量(15)+MACD(15)+BOLL(15)+量价(10)+趋势(20)+MFI(15)+背离(10) = 100
_WEIGHTS = {"momentum": 15, "macd": 15, "boll": 15, "vol": 10, "trend": 20, "mfi": 15, "div": 10}

_BUY = "[买] "
_SELL = "[卖] "


def _safe_last(series: pd.Series | np.ndarray) -> float | None:
    """Get last non-NaN value from a series."""
    val = series.iloc[-1] if isinstance(series, pd.Series) else series[-1]
    return None if np.isnan(val) else round(float(val), 4)


def _prev(series: pd.Series | np.ndarray, offset: int = 1) -> float | None:
    """Get value at offset from end."""
    if len(series) < offset + 1:
        return None
    val = series.iloc[-(offset + 1)] if isinstance(series, pd.Series) else series[-(offset + 1)]
    return None if np.isnan(val) else round(float(val), 4)


def _calc_ema_trend(
    close: pd.Series, current_price: float, *, max_score: float
) -> tuple[float, str | None, list[str]]:
    """Calculate EMA trend score. Returns (score, signal, signals)."""
    signals: list[str] = []

    close_arr = close.to_numpy()
    ema5 = talib.EMA(close_arr, timeperiod=5)
    ema10 = talib.EMA(close_arr, timeperiod=10)
    ema20 = talib.EMA(close_arr, timeperiod=20)
    ema60 = talib.EMA(close_arr, timeperiod=60) if len(close_arr) >= 60 else None

    e5 = _safe_last(ema5)
    e10 = _safe_last(ema10)
    e20 = _safe_last(ema20)
    e60 = _safe_last(ema60) if ema60 is not None else None

    if e5 is None or e10 is None or e20 is None:
        return 0, None, signals

    # EMA crossover detection (MA5 vs MA10)
    e5_prev = _prev(ema5)
    e10_prev = _prev(ema10)
    if e5_prev is not None and e10_prev is not None:
        if e5_prev <= e10_prev and e5 > e10:
            signals.append(f"{_BUY}EMA金叉 (MA5上穿MA10)")
        elif e5_prev >= e10_prev and e5 < e10:
            signals.append(f"{_SELL}EMA死叉 (MA5下穿MA10)")

    above_count = sum([
        current_price > e5,
        current_price > e10,
        current_price > e20,
        current_price > e60 if e60 is not None else False,
    ])
    bullish_align = e5 > e10 > e20

    if bullish_align and above_count >= 3:
        signal = "多头排列 (价>MA5>MA10>MA20)"
        signals.append(f"{_BUY}EMA多头排列")
        return max_score, signal, signals
    if above_count >= 3:
        return max_score * 0.7, f"偏多 (站上{above_count}条均线)", signals
    if above_count == 2:
        return max_score * 0.4, f"震荡 (站上{above_count}条均线)", signals
    if above_count == 1:
        return max_score * 0.2, f"偏空 (仅站上{above_count}条均线)", signals

    bearish_align = e5 < e10 < e20
    if bearish_align:
        signals.append(f"{_SELL}EMA空头排列")
        return 0, "空头排列 (价<MA5<MA10<MA20)", signals
    return max_score * 0.1, "弱势 (跌破全部均线)", signals


def _calc_momentum(
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
    *,
    max_score: float,
) -> tuple[float, str | None, list[str]]:
    """Merged RSI + KDJ momentum dimension. RSI 60% + KDJ 40%."""
    signals: list[str] = []

    # RSI sub-score (0~1)
    rsi = talib.RSI(close.to_numpy(), timeperiod=14)
    rsi_now = _safe_last(rsi)
    rsi_ratio = 0.25  # default neutral

    if rsi_now is not None:
        if rsi_now < 30:
            rsi_ratio = 1.0
            signals.append(f"{_BUY}RSI超卖 ({rsi_now:.1f})")
        elif rsi_now < 40:
            rsi_ratio = 0.6
        elif rsi_now <= 60:
            rsi_ratio = 0.25
        elif rsi_now <= 70:
            rsi_ratio = 0.1
        else:
            rsi_ratio = 0.0
            signals.append(f"{_SELL}RSI超买 ({rsi_now:.1f})")

    # KDJ sub-score (0~1)
    k, d = talib.STOCH(
        high.to_numpy(), low.to_numpy(), close.to_numpy(),
        fastk_period=9, slowk_period=3, slowd_period=3,
    )
    j = 3 * k - 2 * d
    k_now, d_now, j_now = _safe_last(k), _safe_last(d), _safe_last(j)
    k_prev, d_prev = _prev(k), _prev(d)
    kdj_ratio = 0.25  # default neutral

    if k_now is not None and d_now is not None:
        golden_cross = (
            k_prev is not None and d_prev is not None and k_prev <= d_prev and k_now > d_now
        )
        death_cross = (
            k_prev is not None and d_prev is not None and k_prev >= d_prev and k_now < d_now
        )

        if golden_cross and (j_now is None or j_now < 50):
            kdj_ratio = 1.0
            signals.append(f"{_BUY}KDJ金叉 (K={k_now:.1f})")
        elif j_now is not None and j_now < 20:
            kdj_ratio = 0.75
            signals.append(f"{_BUY}KDJ超卖 (J={j_now:.1f})")
        elif death_cross and j_now is not None and j_now > 70:
            kdj_ratio = 0.0
            signals.append(f"{_SELL}KDJ死叉 (J={j_now:.1f})")
        elif j_now is not None and j_now > 80:
            kdj_ratio = 0.0
            signals.append(f"{_SELL}KDJ超买 (J={j_now:.1f})")
        elif k_now > d_now:
            kdj_ratio = 0.4
        else:
            kdj_ratio = 0.15

    # Weighted: RSI 60% + KDJ 40%
    combined = rsi_ratio * 0.6 + kdj_ratio * 0.4
    score = round(max_score * combined, 1)

    # Build signal text
    parts: list[str] = []
    if rsi_now is not None:
        parts.append(f"RSI={rsi_now:.0f}")
    if j_now is not None:
        parts.append(f"J={j_now:.0f}")
    signal = " / ".join(parts) if parts else None

    return score, signal, signals


def _calc_divergence(
    close: pd.Series, macd_hist: np.ndarray, *, max_score: float, lookback: int = 20
) -> tuple[float, str | None, list[str]]:
    """Detect MACD histogram divergence. Returns (score, signal, signals)."""
    signals: list[str] = []

    n = len(close)
    if n < lookback + 1 or len(macd_hist) < lookback + 1:
        return max_score * 0.5, None, signals

    # Recent window (exclude current bar for comparison)
    window_close = close.iloc[-(lookback + 1) : -1]
    window_hist = macd_hist[-(lookback + 1) : -1]
    cur_close = float(close.iloc[-1])
    cur_hist = float(macd_hist[-1]) if not np.isnan(macd_hist[-1]) else None

    if cur_hist is None:
        return max_score * 0.5, None, signals

    # Find min/max close in lookback window
    min_idx = int(window_close.to_numpy().argmin())
    max_idx = int(window_close.to_numpy().argmax())
    prev_low = float(window_close.iloc[min_idx])
    prev_high = float(window_close.iloc[max_idx])
    hist_at_low = float(window_hist[min_idx]) if not np.isnan(window_hist[min_idx]) else None
    hist_at_high = float(window_hist[max_idx]) if not np.isnan(window_hist[max_idx]) else None

    # Bottom divergence: price near/below previous low, but MACD hist higher
    if hist_at_low is not None and cur_close <= prev_low * 1.02 and cur_hist > hist_at_low:
        signals.append(f"{_BUY}MACD底背离")
        return max_score, "底背离 (价创新低+MACD抬升)", signals

    # Top divergence: price near/above previous high, but MACD hist lower
    if hist_at_high is not None and cur_close >= prev_high * 0.98 and cur_hist < hist_at_high:
        signals.append(f"{_SELL}MACD顶背离")
        return 0, "顶背离 (价创新高+MACD走低)", signals

    # No divergence detected
    return max_score * 0.5, "无背离", signals


def _calc_mfi(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    *,
    max_score: float,
) -> tuple[float, str | None, list[str]]:
    """Calculate MFI (Money Flow Index) dimension. Returns (score, signal, signals)."""
    signals: list[str] = []

    mfi = talib.MFI(
        high.to_numpy().astype(float),
        low.to_numpy().astype(float),
        close.to_numpy().astype(float),
        volume.to_numpy().astype(float),
        timeperiod=14,
    )
    mfi_now = _safe_last(mfi)

    if mfi_now is None:
        return max_score * 0.5, None, signals

    if mfi_now < 20:
        score = max_score
        signal = f"资金大幅流入 (MFI={mfi_now:.0f})"
        signals.append(f"{_BUY}MFI超卖 ({mfi_now:.0f})")
    elif mfi_now < 40:
        score = max_score * 0.67
        signal = f"资金流入 (MFI={mfi_now:.0f})"
    elif mfi_now <= 60:
        score = max_score * 0.47
        signal = f"资金中性 (MFI={mfi_now:.0f})"
    elif mfi_now <= 80:
        score = max_score * 0.2
        signal = f"资金流出 (MFI={mfi_now:.0f})"
    else:
        score = 0
        signal = f"资金大幅流出 (MFI={mfi_now:.0f})"
        signals.append(f"{_SELL}MFI超买 ({mfi_now:.0f})")

    return round(score, 1), signal, signals


def calc_score(symbol: str, *, count: int = 60) -> ScoreResult:
    """
    Calculate multi-indicator resonance score.

    7 dimensions (unified for stock & ETF):
    动量(RSI+KDJ) + MACD + BOLL + 量价 + 趋势(EMA) + MFI(资金流) + 背离
    """
    w = _WEIGHTS

    candles = get_history(symbol, count=count)
    if not candles or len(candles) < 20:
        got = len(candles) if candles else 0
        raise IndicatorError(f"Insufficient history for {symbol} (need>=20, got {got})")

    df = candles_to_df(candles)

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]
    current_price = float(close.iloc[-1])

    dimensions: list[ScoreDimension] = []
    signals: list[str] = []
    total = 0.0

    # --- 1. Momentum (RSI + KDJ merged) ---
    mom_max = float(w["momentum"])
    mom_score, mom_signal, mom_sigs = _calc_momentum(
        close, high, low, max_score=mom_max
    )
    signals.extend(mom_sigs)
    total += mom_score
    dimensions.append(
        ScoreDimension(name="动量", score=mom_score, max_score=mom_max, signal=mom_signal)
    )

    # --- 2. MACD (15 points) ---
    close_arr = close.to_numpy()
    macd, macd_signal, macd_hist = talib.MACD(
        close_arr, fastperiod=12, slowperiod=26, signalperiod=9,
    )
    macd_now = _safe_last(macd)
    signal_now = _safe_last(macd_signal)
    hist_now = _safe_last(macd_hist)
    hist_prev = _prev(macd_hist)

    macd_score = 0.0
    macd_sig = None

    if macd_now is not None and signal_now is not None:
        macd_prev_val = _prev(macd)
        signal_prev_val = _prev(macd_signal)
        golden = (
            macd_prev_val is not None
            and signal_prev_val is not None
            and macd_prev_val <= signal_prev_val
            and macd_now > signal_now
        )
        death = (
            macd_prev_val is not None
            and signal_prev_val is not None
            and macd_prev_val >= signal_prev_val
            and macd_now < signal_now
        )

        if golden:
            macd_score = 15
            macd_sig = "金叉"
            signals.append(f"{_BUY}MACD金叉 (DIF={macd_now:.4f})")
        elif death:
            macd_score = 0
            macd_sig = "死叉"
            signals.append(f"{_SELL}MACD死叉 (DIF={macd_now:.4f})")
        elif hist_now is not None and hist_prev is not None and hist_now > 0 and hist_prev <= 0:
            macd_score = 10
            macd_sig = "柱翻红"
            signals.append(f"{_BUY}MACD柱翻红")
        elif hist_now is not None and hist_prev is not None and hist_now < 0 and hist_prev >= 0:
            macd_score = 0
            macd_sig = "柱翻绿"
            signals.append(f"{_SELL}MACD柱翻绿")
        elif macd_now > signal_now and hist_now is not None and hist_now > 0:
            macd_score = 8
            macd_sig = "多头"
        else:
            macd_score = 2
            macd_sig = "空头"

    total += macd_score
    dimensions.append(ScoreDimension(name="MACD", score=macd_score, max_score=15, signal=macd_sig))

    # --- 3. BOLL (15 points) ---
    upper, middle, lower = talib.BBANDS(close_arr, timeperiod=20, nbdevup=2, nbdevdn=2)
    upper_now = _safe_last(upper)
    lower_now = _safe_last(lower)
    middle_now = _safe_last(middle)

    boll_score = 0.0
    boll_signal = None

    if upper_now is not None and lower_now is not None and middle_now is not None:
        bandwidth = upper_now - lower_now
        position_pct = ((current_price - lower_now) / bandwidth * 100) if bandwidth > 0 else 50

        # Bandwidth squeeze: bandwidth / middle < 5% → volatility contraction
        bw_pct = (bandwidth / middle_now * 100) if middle_now > 0 else 999
        if bw_pct < 5:
            signals.append(f"[警] 布林收窄 (带宽{bw_pct:.1f}%，预示变盘)")

        if position_pct < 10:
            boll_score = 15
            boll_signal = f"下轨反弹 (位置{position_pct:.0f}%)"
            signals.append(f"{_BUY}布林下轨反弹 ({position_pct:.0f}%)")
        elif position_pct < 30:
            boll_score = 10
            boll_signal = f"偏下轨 (位置{position_pct:.0f}%)"
        elif position_pct < 50:
            boll_score = 7
            boll_signal = f"中轨下方 (位置{position_pct:.0f}%)"
        elif position_pct < 70:
            boll_score = 5
            boll_signal = f"中轨上方 (位置{position_pct:.0f}%)"
        elif position_pct < 90:
            boll_score = 2
            boll_signal = f"偏上轨 (位置{position_pct:.0f}%)"
        else:
            boll_score = 0
            boll_signal = f"触及上轨 (位置{position_pct:.0f}%)"
            signals.append(f"{_SELL}布林触及上轨 ({position_pct:.0f}%)")

    total += boll_score
    dimensions.append(
        ScoreDimension(name="BOLL", score=boll_score, max_score=15, signal=boll_signal)
    )

    # --- 4. Volume surge ---
    vol_max = float(w["vol"])
    turnover = df["turnover"].astype(float) if "turnover" in df.columns else None
    vol_score = 0.0
    vol_signal = None

    if turnover is not None and len(turnover) >= 6:
        avg_vol = turnover.iloc[-6:-1].mean()
        cur_vol = turnover.iloc[-1]
        vol_ratio = cur_vol / avg_vol if avg_vol > 0 else 1
        prev_close = close.iloc[-2]
        price_change = (close.iloc[-1] - prev_close) / prev_close * 100 if prev_close > 0 else 0

        if vol_ratio > 2.0 and price_change > 3:
            vol_score = vol_max
            vol_signal = f"放量上涨 (量比{vol_ratio:.1f}x, +{price_change:.1f}%)"
            signals.append(f"{_BUY}放量突破 (量比{vol_ratio:.1f}x)")
        elif vol_ratio > 1.5 and price_change > 1:
            vol_score = vol_max * 0.67
            vol_signal = f"温和放量 (量比{vol_ratio:.1f}x)"
        elif vol_ratio > 2.0 and price_change < -3:
            vol_score = 0
            vol_signal = f"放量下跌 (量比{vol_ratio:.1f}x, {price_change:.1f}%)"
            signals.append(f"{_SELL}放量下跌 (量比{vol_ratio:.1f}x)")
        elif vol_ratio < 0.5:
            vol_score = vol_max * 0.2
            vol_signal = f"缩量 (量比{vol_ratio:.1f}x)"
        else:
            vol_score = vol_max * 0.33
            vol_signal = f"正常 (量比{vol_ratio:.1f}x)"

    total += vol_score
    dimensions.append(
        ScoreDimension(name="量价", score=vol_score, max_score=vol_max, signal=vol_signal)
    )

    # --- 5. EMA Trend ---
    trend_max = float(w["trend"])
    trend_score, trend_signal, trend_sigs = _calc_ema_trend(
        close, current_price, max_score=trend_max
    )
    signals.extend(trend_sigs)
    total += trend_score
    dimensions.append(
        ScoreDimension(name="趋势", score=trend_score, max_score=trend_max, signal=trend_signal)
    )

    # --- 6. MFI (Money Flow Index) ---
    mfi_max = float(w["mfi"])
    mfi_score, mfi_signal, mfi_sigs = _calc_mfi(
        high, low, close, volume, max_score=mfi_max
    )
    signals.extend(mfi_sigs)
    total += mfi_score
    dimensions.append(
        ScoreDimension(name="资金流", score=mfi_score, max_score=mfi_max, signal=mfi_signal)
    )

    # --- 7. Divergence (MACD histogram) ---
    div_max = float(w["div"])
    div_score, div_signal, div_sigs = _calc_divergence(
        close, macd_hist, max_score=div_max
    )
    signals.extend(div_sigs)
    total += div_score
    dimensions.append(
        ScoreDimension(name="背离", score=div_score, max_score=div_max, signal=div_signal)
    )

    total_score = round(total, 1)

    # --- ADX ---
    adx_val = None
    high_arr, low_arr = high.to_numpy(), low.to_numpy()
    adx_series = talib.ADX(high_arr, low_arr, close_arr, timeperiod=14)
    adx_last = _safe_last(adx_series)
    if adx_last is not None:
        adx_val = round(adx_last, 1)

    # --- ATR stop-loss / take-profit ---
    atr_val = None
    stop_loss = None
    take_profit = None
    rr_ratio = None

    atr_series = talib.ATR(high_arr, low_arr, close_arr, timeperiod=14)
    atr_last = _safe_last(atr_series)
    if atr_last is not None and atr_last > 0:
        atr_val = round(atr_last, 4)
        stop_loss = round(current_price - atr_last * 2.0, 4)
        take_profit = round(current_price + atr_last * 3.0, 4)
        risk = current_price - stop_loss
        rr_ratio = round((take_profit - current_price) / risk, 1) if risk > 0 else None

    return ScoreResult(
        symbol=symbol,
        total_score=total_score,
        dimensions=dimensions,
        signals=signals,
        adx=adx_val,
        atr=atr_val,
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_reward_ratio=rr_ratio,
    )
