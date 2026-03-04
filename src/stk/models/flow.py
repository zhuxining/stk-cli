"""Money flow models."""

from decimal import Decimal

from pydantic import BaseModel


class FlowLine(BaseModel):
    """Intraday capital flow point (minute-level)."""

    timestamp: str
    inflow: Decimal


class MoneyFlow(BaseModel):
    """Capital distribution — large/medium/small order breakdown."""

    symbol: str
    large_in: Decimal | None = None
    large_out: Decimal | None = None
    medium_in: Decimal | None = None
    medium_out: Decimal | None = None
    small_in: Decimal | None = None
    small_out: Decimal | None = None
    intraday: list[FlowLine] | None = None


class SectorFlow(BaseModel):
    """Sector-level money flow data."""

    sector: str
    change_pct: Decimal | None = None
    main_net: Decimal | None = None
