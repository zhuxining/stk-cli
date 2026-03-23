"""Watchlist scan models."""

from decimal import Decimal

from pydantic import BaseModel


class ScanItem(BaseModel):
    """Single security result in a watchlist scan."""

    symbol: str
    name: str = ""
    last: Decimal | None = None
    change_pct: Decimal | None = None
    source: str = "realtime"  # "realtime" | "last_close"
    score: float | None = None
    signals: list[str] = []  # "[买] ..." / "[卖] ..." / "[警] ..."
    score_detail: dict[str, str] = {}  # {维度名: signal文本}
    # Valuation fields
    pe_ttm: Decimal | None = None
    pb: Decimal | None = None
    dividend_yield: Decimal | None = None
    # Market dynamics
    volume_ratio: Decimal | None = None
    turnover_rate: Decimal | None = None  # 换手率 (%)
    amplitude: Decimal | None = None  # 振幅 (%)
    # Change rates
    change_5d: Decimal | None = None  # 5日涨跌幅 (%)
    change_10d: Decimal | None = None  # 10日涨跌幅 (%)
    ytd_change_rate: Decimal | None = None  # 年初至今涨幅 (%)
    # Trend
    adx: float | None = None
    # ATR risk control
    atr: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    risk_reward_ratio: float | None = None
    # Capital flow (from calc_indexes, 万元)
    capital_flow: Decimal | None = None
    # Company profile
    main_business: str | None = None


class ScanResult(BaseModel):
    """Batch scan result for a watchlist group."""

    group_name: str
    total: int
    items: list[ScanItem]
