"""Money flow models."""

from decimal import Decimal

from pydantic import BaseModel


class FlowLine(BaseModel):
    """Intraday capital flow point (minute-level)."""

    timestamp: str
    inflow: Decimal


class StockFlow(BaseModel):
    """Individual stock money flow — realtime distribution + recent history."""

    symbol: str
    # Realtime distribution (longport)
    large_in: Decimal | None = None
    large_out: Decimal | None = None
    medium_in: Decimal | None = None
    medium_out: Decimal | None = None
    small_in: Decimal | None = None
    small_out: Decimal | None = None
    intraday: list[FlowLine] | None = None
    # Recent daily history (akshare) — latest N days
    history: list[dict[str, Decimal | None]] | None = None


class FlowRankItem(BaseModel):
    """A single item in fund flow ranking."""

    code: str
    name: str
    metrics: dict[str, Decimal | None]


class FlowRank(BaseModel):
    """Fund flow ranking result."""

    scope: str  # "stock" / "main" / "sector" / "concept"
    period: str
    items: list[FlowRankItem]


class SectorFlowDay(BaseModel):
    """One day of sector/concept historical fund flow."""

    date: str
    metrics: dict[str, Decimal | None]


class SectorFlowHist(BaseModel):
    """Sector or concept historical fund flow."""

    name: str
    type: str  # "sector" / "concept"
    days: list[SectorFlowDay]


class SectorFlowDetail(BaseModel):
    """Individual stocks' fund flow within a sector."""

    sector: str
    period: str
    items: list[FlowRankItem]
