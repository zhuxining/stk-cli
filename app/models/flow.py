"""Money flow models."""

from decimal import Decimal

from pydantic import BaseModel


class MoneyFlow(BaseModel):
    symbol: str
    name: str = ""
    main_net: Decimal | None = None
    super_large_net: Decimal | None = None
    large_net: Decimal | None = None
    medium_net: Decimal | None = None
    small_net: Decimal | None = None


class SectorFlow(BaseModel):
    sector: str
    change_pct: Decimal | None = None
    main_net: Decimal | None = None
