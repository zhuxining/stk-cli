"""Multi-indicator resonance scoring service."""

from decimal import Decimal

from loguru import logger
import numpy as np
import pandas as pd
import talib

from stk.errors import IndicatorError, SourceError
from stk.models.score import ScoreDimension, ScoreResult
from stk.services.history import candles_to_df, get_history


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


def calc_score(symbol: str, *, count: int = 60) -> ScoreResult:
    """
    Calculate multi-indicator resonance score for a stock.

    Scoring system (100 points total):
    - RSI signal:      20 points
    - KDJ signal:      20 points
    - MACD signal:     15 points
    - BOLL signal:     15 points
    - Volume surge:    15 points
    - Money flow:      15 points

    Also calculates ATR-based stop-loss/take-profit when possible.
    """
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

    # --- 1. RSI (20 points) ---
    rsi = talib.RSI(close, timeperiod=14)
    rsi_now = _safe_last(rsi)
    rsi_score = 0.0
    rsi_signal = None

    if rsi_now is not None:
        if rsi_now < 30:
            rsi_score = 20
            rsi_signal = f"超卖 ({rsi_now:.1f})"
            buy_signals.append(f"RSI超卖 ({rsi_now:.1f})")
        elif rsi_now < 40:
            rsi_score = 12
            rsi_signal = f"偏低 ({rsi_now:.1f})"
        elif rsi_now <= 60:
            rsi_score = 5
            rsi_signal = f"中性 ({rsi_now:.1f})"
        elif rsi_now <= 70:
            rsi_score = 2
            rsi_signal = f"偏高 ({rsi_now:.1f})"
        else:
            rsi_score = 0
            rsi_signal = f"超买 ({rsi_now:.1f})"
            sell_signals.append(f"RSI超买 ({rsi_now:.1f})")

    total += rsi_score
    dimensions.append(ScoreDimension(name="RSI", score=rsi_score, max_score=20, signal=rsi_signal))

    # --- 2. KDJ (20 points) ---
    k, d = talib.STOCH(high, low, close, fastk_period=9, slowk_period=3, slowd_period=3)
    j = 3 * k - 2 * d
    k_now, d_now, j_now = _safe_last(k), _safe_last(d), _safe_last(j)
    k_prev, d_prev = _prev(k), _prev(d)

    kdj_score = 0.0
    kdj_signal = None

    if k_now is not None and d_now is not None:
        golden_cross = k_prev is not None and d_prev is not None and k_prev <= d_prev and k_now > d_now
        death_cross = k_prev is not None and d_prev is not None and k_prev >= d_prev and k_now < d_now

        if golden_cross and (j_now is None or j_now < 50):
            kdj_score = 20
            kdj_signal = f"金叉 (K={k_now:.1f}, J={j_now:.1f})" if j_now else "金叉"
            buy_signals.append(f"KDJ金叉 (K={k_now:.1f})")
        elif j_now is not None and j_now < 20:
            kdj_score = 15
            kdj_signal = f"超卖 (J={j_now:.1f})"
            buy_signals.append(f"KDJ超卖 (J={j_now:.1f})")
        elif death_cross and j_now is not None and j_now > 70:
            kdj_score = 0
            kdj_signal = f"死叉 (K={k_now:.1f}, J={j_now:.1f})"
            sell_signals.append(f"KDJ死叉 (J={j_now:.1f})")
        elif j_now is not None and j_now > 80:
            kdj_score = 0
            kdj_signal = f"超买 (J={j_now:.1f})"
            sell_signals.append(f"KDJ超买 (J={j_now:.1f})")
        elif k_now > d_now:
            kdj_score = 8
            kdj_signal = f"多头 (K={k_now:.1f})"
        else:
            kdj_score = 3
            kdj_signal = f"空头 (K={k_now:.1f})"

    total += kdj_score
    dimensions.append(ScoreDimension(name="KDJ", score=kdj_score, max_score=20, signal=kdj_signal))

    # --- 3. MACD (15 points) ---
    macd, macd_signal, macd_hist = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
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

    # --- 4. BOLL (15 points) ---
    upper, middle, lower = talib.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2)
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

    # --- 5. Volume surge (15 points) ---
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
            vol_score = 15
            vol_signal = f"放量上涨 (量比{vol_ratio:.1f}x, +{price_change:.1f}%)"
            buy_signals.append(f"放量突破 (量比{vol_ratio:.1f}x)")
        elif vol_ratio > 1.5 and price_change > 1:
            vol_score = 10
            vol_signal = f"温和放量 (量比{vol_ratio:.1f}x)"
        elif vol_ratio > 2.0 and price_change < -3:
            vol_score = 0
            vol_signal = f"放量下跌 (量比{vol_ratio:.1f}x, {price_change:.1f}%)"
            sell_signals.append(f"放量下跌 (量比{vol_ratio:.1f}x)")
        elif vol_ratio < 0.5:
            vol_score = 3
            vol_signal = f"缩量 (量比{vol_ratio:.1f}x)"
        else:
            vol_score = 5
            vol_signal = f"正常 (量比{vol_ratio:.1f}x)"

    total += vol_score
    dimensions.append(ScoreDimension(name="量价", score=vol_score, max_score=15, signal=vol_signal))

    # --- 6. Money flow (15 points) ---
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

    # --- ATR stop-loss / take-profit ---
    atr_val = None
    stop_loss = None
    take_profit = None
    rr_ratio = None

    atr_series = talib.ATR(high, low, close, timeperiod=14)
    atr_last = _safe_last(atr_series)
    if atr_last is not None and atr_last > 0:
        atr_val = round(atr_last, 4)
        stop_loss = round(current_price - atr_last * 2.0, 4)
        take_profit = round(current_price + atr_last * 3.0, 4)
        risk = current_price - stop_loss
        rr_ratio = round((take_profit - current_price) / risk, 1) if risk > 0 else None

    # --- Rating ---
    rating = _get_rating(total)

    return ScoreResult(
        symbol=symbol,
        total_score=round(total, 1),
        rating=rating,
        dimensions=dimensions,
        buy_signals=buy_signals,
        sell_signals=sell_signals,
        atr=atr_val,
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_reward_ratio=rr_ratio,
    )


def _get_rating(score: float) -> str:
    """Convert score to rating."""
    if score >= 85:
        return "A+"
    if score >= 70:
        return "A"
    if score >= 60:
        return "B+"
    if score >= 50:
        return "B"
    return "C"
