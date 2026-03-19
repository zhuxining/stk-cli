"""Multi-indicator resonance scoring service."""

from decimal import Decimal

from loguru import logger
import numpy as np
import pandas as pd
import talib

from stk.errors import IndicatorError, SourceError
from stk.models.score import ScoreDimension, ScoreResult
from stk.services.history import candles_to_df, get_history
from stk.utils.symbol import is_etf

# --- Weight configs ---
# Stock: 动量(15)+MACD(15)+BOLL(15)+量价(10)+趋势(20)+资金(15)+背离(10) = 100
# ETF:   动量(10)+MACD(15)+BOLL(15)+量价(10)+趋势(25)+背离(10) = 85 → normalize
_W_STOCK = {"momentum": 15, "macd": 15, "boll": 15, "vol": 10, "trend": 20, "flow": 15, "div": 10}
_W_ETF = {"momentum": 10, "macd": 15, "boll": 15, "vol": 10, "trend": 25, "div": 10}


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
) -> tuple[float, str | None, list[str], list[str]]:
    """Calculate EMA trend score. Returns (score, signal, buy_signals, sell_signals)."""
    buy_signals: list[str] = []
    sell_signals: list[str] = []

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
        return 0, None, buy_signals, sell_signals

    above_count = sum([
        current_price > e5,
        current_price > e10,
        current_price > e20,
        current_price > e60 if e60 is not None else False,
    ])
    bullish_align = e5 > e10 > e20

    if bullish_align and above_count >= 3:
        signal = "多头排列 (价>MA5>MA10>MA20)"
        buy_signals.append("EMA多头排列")
        return max_score, signal, buy_signals, sell_signals
    if above_count >= 3:
        return max_score * 0.7, f"偏多 (站上{above_count}条均线)", buy_signals, sell_signals
    if above_count == 2:
        return max_score * 0.4, f"震荡 (站上{above_count}条均线)", buy_signals, sell_signals
    if above_count == 1:
        return max_score * 0.2, f"偏空 (仅站上{above_count}条均线)", buy_signals, sell_signals

    bearish_align = e5 < e10 < e20
    if bearish_align:
        sell_signals.append("EMA空头排列")
        return 0, "空头排列 (价<MA5<MA10<MA20)", buy_signals, sell_signals
    return max_score * 0.1, "弱势 (跌破全部均线)", buy_signals, sell_signals


def _calc_momentum(
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
    *,
    max_score: float,
) -> tuple[float, str | None, list[str], list[str]]:
    """Merged RSI + KDJ momentum dimension. RSI 60% + KDJ 40%."""
    buy_signals: list[str] = []
    sell_signals: list[str] = []

    # RSI sub-score (0~1)
    rsi = talib.RSI(close.to_numpy(), timeperiod=14)
    rsi_now = _safe_last(rsi)
    rsi_ratio = 0.25  # default neutral

    if rsi_now is not None:
        if rsi_now < 30:
            rsi_ratio = 1.0
            buy_signals.append(f"RSI超卖 ({rsi_now:.1f})")
        elif rsi_now < 40:
            rsi_ratio = 0.6
        elif rsi_now <= 60:
            rsi_ratio = 0.25
        elif rsi_now <= 70:
            rsi_ratio = 0.1
        else:
            rsi_ratio = 0.0
            sell_signals.append(f"RSI超买 ({rsi_now:.1f})")

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
            buy_signals.append(f"KDJ金叉 (K={k_now:.1f})")
        elif j_now is not None and j_now < 20:
            kdj_ratio = 0.75
            buy_signals.append(f"KDJ超卖 (J={j_now:.1f})")
        elif death_cross and j_now is not None and j_now > 70:
            kdj_ratio = 0.0
            sell_signals.append(f"KDJ死叉 (J={j_now:.1f})")
        elif j_now is not None and j_now > 80:
            kdj_ratio = 0.0
            sell_signals.append(f"KDJ超买 (J={j_now:.1f})")
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

    return score, signal, buy_signals, sell_signals


def _calc_divergence(
    close: pd.Series, macd_hist: np.ndarray, *, max_score: float, lookback: int = 20
) -> tuple[float, str | None, list[str], list[str]]:
    """Detect MACD histogram divergence. Returns (score, signal, buys, sells)."""
    buy_signals: list[str] = []
    sell_signals: list[str] = []

    n = len(close)
    if n < lookback + 1 or len(macd_hist) < lookback + 1:
        return max_score * 0.5, None, buy_signals, sell_signals

    # Recent window (exclude current bar for comparison)
    window_close = close.iloc[-(lookback + 1) : -1]
    window_hist = macd_hist[-(lookback + 1) : -1]
    cur_close = float(close.iloc[-1])
    cur_hist = float(macd_hist[-1]) if not np.isnan(macd_hist[-1]) else None

    if cur_hist is None:
        return max_score * 0.5, None, buy_signals, sell_signals

    # Find min/max close in lookback window
    min_idx = int(window_close.to_numpy().argmin())
    max_idx = int(window_close.to_numpy().argmax())
    prev_low = float(window_close.iloc[min_idx])
    prev_high = float(window_close.iloc[max_idx])
    hist_at_low = float(window_hist[min_idx]) if not np.isnan(window_hist[min_idx]) else None
    hist_at_high = float(window_hist[max_idx]) if not np.isnan(window_hist[max_idx]) else None

    # Bottom divergence: price near/below previous low, but MACD hist higher
    if hist_at_low is not None and cur_close <= prev_low * 1.02 and cur_hist > hist_at_low:
        buy_signals.append("MACD底背离")
        return max_score, "底背离 (价创新低+MACD抬升)", buy_signals, sell_signals

    # Top divergence: price near/above previous high, but MACD hist lower
    if hist_at_high is not None and cur_close >= prev_high * 0.98 and cur_hist < hist_at_high:
        sell_signals.append("MACD顶背离")
        return 0, "顶背离 (价创新高+MACD走低)", buy_signals, sell_signals

    # No divergence detected
    return max_score * 0.5, "无背离", buy_signals, sell_signals


def calc_score(symbol: str, *, count: int = 60) -> ScoreResult:
    """
    Calculate multi-indicator resonance score for a stock or ETF.

    6 dimensions (ETF skips flow, compensates with higher trend weight):
    动量(RSI+KDJ) + MACD + BOLL + 量价 + 趋势(EMA) + 背离 [+ 资金(stock only)]
    """
    etf_mode = is_etf(symbol)
    w = _W_ETF if etf_mode else _W_STOCK

    candles = get_history(symbol, count=count)
    if not candles or len(candles) < 20:
        got = len(candles) if candles else 0
        raise IndicatorError(f"Insufficient history for {symbol} (need>=20, got {got})")

    df = candles_to_df(candles)

    close = df["close"]
    high = df["high"]
    low = df["low"]
    current_price = float(close.iloc[-1])

    dimensions: list[ScoreDimension] = []
    buy_signals: list[str] = []
    sell_signals: list[str] = []
    total = 0.0

    # --- 1. Momentum (RSI + KDJ merged) ---
    mom_max = float(w["momentum"])
    mom_score, mom_signal, mom_buys, mom_sells = _calc_momentum(
        close, high, low, max_score=mom_max
    )
    buy_signals.extend(mom_buys)
    sell_signals.extend(mom_sells)
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
            buy_signals.append(f"MACD金叉 (DIF={macd_now:.4f})")
        elif death:
            macd_score = 0
            macd_sig = "死叉"
            sell_signals.append(f"MACD死叉 (DIF={macd_now:.4f})")
        elif hist_now is not None and hist_prev is not None and hist_now > 0 and hist_prev <= 0:
            macd_score = 10
            macd_sig = "柱翻红"
            buy_signals.append("MACD柱翻红")
        elif hist_now is not None and hist_prev is not None and hist_now < 0 and hist_prev >= 0:
            macd_score = 0
            macd_sig = "柱翻绿"
            sell_signals.append("MACD柱翻绿")
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

        if position_pct < 10:
            boll_score = 15
            boll_signal = f"下轨反弹 (位置{position_pct:.0f}%)"
            buy_signals.append(f"布林下轨反弹 ({position_pct:.0f}%)")
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
            sell_signals.append(f"布林触及上轨 ({position_pct:.0f}%)")

    total += boll_score
    dimensions.append(
        ScoreDimension(name="BOLL", score=boll_score, max_score=15, signal=boll_signal)
    )

    # --- 4. Volume surge ---
    vol_max = float(w["vol"])
    volume = df["turnover"].astype(float) if "turnover" in df.columns else None
    vol_score = 0.0
    vol_signal = None

    if volume is not None and len(volume) >= 6:
        avg_vol = volume.iloc[-6:-1].mean()
        cur_vol = volume.iloc[-1]
        vol_ratio = cur_vol / avg_vol if avg_vol > 0 else 1
        prev_close = close.iloc[-2]
        price_change = (close.iloc[-1] - prev_close) / prev_close * 100 if prev_close > 0 else 0

        if vol_ratio > 2.0 and price_change > 3:
            vol_score = vol_max
            vol_signal = f"放量上涨 (量比{vol_ratio:.1f}x, +{price_change:.1f}%)"
            buy_signals.append(f"放量突破 (量比{vol_ratio:.1f}x)")
        elif vol_ratio > 1.5 and price_change > 1:
            vol_score = vol_max * 0.67
            vol_signal = f"温和放量 (量比{vol_ratio:.1f}x)"
        elif vol_ratio > 2.0 and price_change < -3:
            vol_score = 0
            vol_signal = f"放量下跌 (量比{vol_ratio:.1f}x, {price_change:.1f}%)"
            sell_signals.append(f"放量下跌 (量比{vol_ratio:.1f}x)")
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
    trend_score, trend_signal, trend_buys, trend_sells = _calc_ema_trend(
        close, current_price, max_score=trend_max
    )
    buy_signals.extend(trend_buys)
    sell_signals.extend(trend_sells)
    total += trend_score
    dimensions.append(
        ScoreDimension(name="趋势", score=trend_score, max_score=trend_max, signal=trend_signal)
    )

    # --- 6. Divergence (MACD histogram) ---
    div_max = float(w["div"])
    div_score, div_signal, div_buys, div_sells = _calc_divergence(
        close, macd_hist, max_score=div_max
    )
    buy_signals.extend(div_buys)
    sell_signals.extend(div_sells)
    total += div_score
    dimensions.append(
        ScoreDimension(name="背离", score=div_score, max_score=div_max, signal=div_signal)
    )

    # --- 7. Money flow (stock only) ---
    if not etf_mode:
        flow_score = 0.0
        flow_signal = None

        try:
            from stk.services.flow import get_stock_flow

            flow = get_stock_flow(symbol)
            if flow.large_in is not None and flow.large_out is not None:
                net_large = flow.large_in - flow.large_out
                net_medium = (flow.medium_in or Decimal(0)) - (flow.medium_out or Decimal(0))
                net_main = net_large + net_medium
                net_main_wan = float(net_main) / 10000

                if net_main > 5_000_000:
                    flow_score = 15
                    flow_signal = f"主力大幅流入 (+{net_main_wan:.0f}万)"
                    buy_signals.append(f"主力流入 (+{net_main_wan:.0f}万)")
                elif net_main > 0:
                    flow_score = 8
                    flow_signal = f"主力小幅流入 (+{net_main_wan:.0f}万)"
                elif net_main > -5_000_000:
                    flow_score = 3
                    flow_signal = f"主力小幅流出 ({net_main_wan:.0f}万)"
                else:
                    flow_score = 0
                    flow_signal = f"主力大幅流出 ({net_main_wan:.0f}万)"
                    sell_signals.append(f"主力流出 ({net_main_wan:.0f}万)")
        except (SourceError, Exception) as e:
            logger.debug(f"Flow data unavailable for {symbol}: {e}")
            flow_signal = "数据不可用"

        total += flow_score
        dimensions.append(
            ScoreDimension(name="资金", score=flow_score, max_score=15, signal=flow_signal)
        )

    # Normalize: stock sums to 100 directly; ETF sums to 85, scale to 100
    raw_max = sum(w.values())
    total_score = round(total / raw_max * 100, 1) if raw_max != 100 else round(total, 1)

    # --- ADX trend strength ---
    adx_val = None
    trend_strength = None
    high_arr, low_arr = high.to_numpy(), low.to_numpy()
    adx_series = talib.ADX(high_arr, low_arr, close_arr, timeperiod=14)
    adx_last = _safe_last(adx_series)
    if adx_last is not None:
        adx_val = round(adx_last, 1)
        trend_strength = "trending" if adx_last >= 25 else "ranging"

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

    # --- Rating ---
    rating = _get_rating(total_score, etf=etf_mode)

    return ScoreResult(
        symbol=symbol,
        total_score=total_score,
        rating=rating,
        mode="etf" if etf_mode else "stock",
        dimensions=dimensions,
        buy_signals=buy_signals,
        sell_signals=sell_signals,
        trend_strength=trend_strength,
        adx=adx_val,
        atr=atr_val,
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_reward_ratio=rr_ratio,
    )


def _get_rating(score: float, *, etf: bool = False) -> str:
    """Convert score to rating. ETF uses lower thresholds."""
    if etf:
        if score >= 75:
            return "A+"
        if score >= 60:
            return "A"
        if score >= 50:
            return "B+"
        if score >= 40:
            return "B"
        return "C"
    if score >= 80:
        return "A+"
    if score >= 65:
        return "A"
    if score >= 55:
        return "B+"
    if score >= 45:
        return "B"
    return "C"
