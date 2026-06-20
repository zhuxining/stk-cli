"""ETF trading strategy signal models."""

from pydantic import BaseModel


class EtfSignal(BaseModel):
    """ETF trading signal based on zigzag pivot and RSI."""

    symbol: str
    status: str  # "定投区", "网格区", "过热持有区", "观察区"
    rsi: float | None = None
    boll_position_pct: float | None = None
    zigzag_low: float | None = None  # 最近一个 zigzag 低点价格
    zigzag_high: float | None = None  # 最近一个 zigzag 高点价格
    signal: str  # 人类可读的信号说明
