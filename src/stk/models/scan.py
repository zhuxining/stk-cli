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
    rating: str | None = None
    mode: str = "stock"  # "stock" | "etf"
    buy_signals: list[str] = []
    sell_signals: list[str] = []
    alerts: list[str] = []
    # Valuation fields
    pe_ttm: Decimal | None = None
    pb: Decimal | None = None
    total_market_value: Decimal | None = None
    dividend_yield: Decimal | None = None
    volume_ratio: Decimal | None = None
    # Flow summary
    net_main_flow: Decimal | None = None  # 主力净流入（万元）


class ScanResult(BaseModel):
    """Batch scan result for a watchlist group."""

    group_name: str
    total: int
    items: list[ScanItem]
