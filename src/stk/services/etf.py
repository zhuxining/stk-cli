"""ETF trading strategy service — zigzag-based state classification."""

from concurrent.futures import ThreadPoolExecutor, as_completed

from loguru import logger

from stk.models.etf import EtfSignal
from stk.services.indicator import get_daily


def _zigzag(closes: list[float], *, pct: float = 3.0) -> list[dict]:
    """Detect pivot points from close prices using zigzag.

    Args:
        closes: Array of close prices (most recent last).
        pct: Minimum reversal percentage to register a pivot.

    Returns:
        List of pivots sorted by index: [{index, price, type}].
    """
    if len(closes) < 4:
        return []

    pivots: list[dict] = []
    direction = 0  # 1=seek high, -1=seek low

    for i in range(1, len(closes) - 1):
        prev, curr, nxt = closes[i - 1], closes[i], closes[i + 1]

        if curr > prev and curr > nxt:  # Local high
            if not pivots:
                pivots.append({"index": i, "price": curr, "type": "high"})
                direction = -1
            elif direction == -1:  # Extension of uptrend, update if higher
                if curr > pivots[-1]["price"]:
                    pivots[-1] = {"index": i, "price": curr, "type": "high"}
            elif direction == 1:  # Reversal from downtrend
                change = abs(curr - pivots[-1]["price"]) / pivots[-1]["price"] * 100
                if change >= pct:
                    pivots.append({"index": i, "price": curr, "type": "high"})
                    direction = -1

        elif curr < prev and curr < nxt:  # Local low
            if not pivots:
                pivots.append({"index": i, "price": curr, "type": "low"})
                direction = 1
            elif direction == 1:  # Extension of downtrend, update if lower
                if curr < pivots[-1]["price"]:
                    pivots[-1] = {"index": i, "price": curr, "type": "low"}
            elif direction == -1:  # Reversal from uptrend
                change = abs(pivots[-1]["price"] - curr) / pivots[-1]["price"] * 100
                if change >= pct:
                    pivots.append({"index": i, "price": curr, "type": "low"})
                    direction = 1

    return pivots


def _classify(
    pivots: list[dict],
    rsi: float | None,
    boll_position_pct: float | None,
) -> tuple[str, str]:
    """Classify ETF status and generate signal text.

    Returns:
        (status, signal_text)
    """
    lows = [p for p in pivots if p["type"] == "low"]
    highs = [p for p in pivots if p["type"] == "high"]

    has_recent_low = bool(lows)
    has_recent_high = bool(highs)

    if has_recent_low and rsi is not None and rsi < 35:
        return (
            "定投区",
            f"Zigzag 低点 {lows[-1]['price']:.2f}，RSI {rsi:.1f} 超卖，建议定投",
        )

    if has_recent_low and has_recent_high:
        return (
            "网格区",
            f"Zigzag 低点 {lows[-1]['price']:.2f}，高点 {highs[-1]['price']:.2f}，建议网格",
        )

    if has_recent_low:
        return (
            "网格区",
            f"Zigzag 低点 {lows[-1]['price']:.2f}，RSI {rsi:.1f}，建议网格",
        )

    if rsi is not None and rsi > 65:
        return (
            "过热持有区",
            f"RSI {rsi:.1f} 偏热，无新低，持有或分批止盈",
        )

    return ("观察区", "无明确信号，继续观察")


def _calc_boll_position_pct(
    close: float | None,
    upper: float | None,
    middle: float | None,
    lower: float | None,
) -> float | None:
    """Calculate Bollinger position percentage (0-100)."""
    if None in (close, upper, middle, lower):
        return None
    if upper is not None and lower is not None and upper - lower <= 0:
        return None
    return round((close - lower) / (upper - lower) * 100, 1)  # type: ignore


def classify_etf(symbol: str) -> EtfSignal:
    """Classify a single ETF symbol into a trading state.

    1. Fetch 60 days of daily data
    2. Run zigzag on close prices
    3. Classify state based on pivots + RSI
    """
    result = get_daily(symbol, count=60)
    closes = [float(d["close"]) for d in result.days if d.get("close") is not None]
    pivots = _zigzag(closes, pct=3.0)

    latest = result.days[-1]
    rsi = latest.get("RSI")
    boll_position = _calc_boll_position_pct(
        latest.get("close"),
        latest.get("upper"),
        latest.get("middle"),
        latest.get("lower"),
    )

    status, signal_text = _classify(pivots, rsi, boll_position)

    lows = [p for p in pivots if p["type"] == "low"]
    highs = [p for p in pivots if p["type"] == "high"]

    return EtfSignal(
        symbol=symbol,
        status=status,
        rsi=rsi,
        boll_position_pct=boll_position,
        zigzag_low=lows[-1]["price"] if lows else None,
        zigzag_high=highs[-1]["price"] if highs else None,
        signal=signal_text,
    )


def classify_watchlist(name: str) -> list[EtfSignal]:
    """Classify all symbols in a watchlist group."""
    from stk.services.watchlist import get_watchlist

    watchlist = get_watchlist(name)
    symbols = [s.symbol for s in watchlist.securities]

    signals: list[EtfSignal] = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(classify_etf, symbol): symbol for symbol in symbols}
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                signals.append(future.result())
            except Exception as err:
                logger.debug(f"Classification failed for {symbol}: {err}")

    signals.sort(key=lambda s: ("定投区", "网格区", "过热持有区", "观察区").index(s.status))
    return signals
