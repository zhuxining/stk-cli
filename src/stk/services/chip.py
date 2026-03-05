"""Chip distribution service — akshare (A-share only)."""

from decimal import Decimal

import akshare as ak

from stk.errors import SourceError
from stk.models.chip import ChipDistribution, ChipSlice
from stk.utils.symbol import to_longport_symbol


def get_chip_distribution(symbol: str) -> ChipDistribution:
    """Get chip cost distribution from akshare."""
    lp_symbol = to_longport_symbol(symbol)
    ak_symbol = lp_symbol.split(".")[0] if "." in lp_symbol else lp_symbol

    try:
        df = ak.stock_cyq_em(symbol=ak_symbol, adjust="")

        if df.empty:
            raise SourceError(f"No chip distribution data for {symbol}")

        row = df.iloc[-1]  # latest date

        return ChipDistribution(
            symbol=lp_symbol,
            avg_cost=Decimal(str(row["平均成本"])),
            profit_ratio=Decimal(str(row["获利比例"])),
            concentration=Decimal(str(row["90集中度"])),
            chips=[
                ChipSlice(
                    date=str(row["日期"]),
                    cost_90_low=Decimal(str(row["90成本-低"])),
                    cost_90_high=Decimal(str(row["90成本-高"])),
                    cost_70_low=Decimal(str(row["70成本-低"])),
                    cost_70_high=Decimal(str(row["70成本-高"])),
                    concentration_70=Decimal(str(row["70集中度"])),
                )
            ],
        )
    except SourceError:
        raise
    except Exception as e:
        raise SourceError(f"Failed to fetch chip distribution for {symbol}: {e}") from e
