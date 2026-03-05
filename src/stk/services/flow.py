"""Money flow service via longport (stock) + akshare (sector/concept)."""

from decimal import Decimal

import akshare as ak

from stk.deps import get_longport_ctx
from stk.errors import SourceError
from stk.models.common import TargetType
from stk.models.flow import FlowLine, MoneyFlow, SectorFlow
from stk.services.symbol import to_longport_symbol

_SECTOR_TYPE_MAP = {
    TargetType.SECTOR: "行业资金流",
    TargetType.CONCEPT: "概念资金流",
}


def get_flow(
    symbol: str,
    *,
    target_type: TargetType = TargetType.STOCK,
) -> MoneyFlow | SectorFlow:
    """Get money flow data from longport (stock) or akshare (sector/concept)."""
    if target_type in (TargetType.SECTOR, TargetType.CONCEPT):
        return _get_sector_flow(symbol, target_type)

    if target_type != TargetType.STOCK:
        raise NotImplementedError(f"Flow for {target_type.value} not yet implemented")

    try:
        ctx = get_longport_ctx()
        lp_symbol = to_longport_symbol(symbol)

        dist = ctx.capital_distribution(lp_symbol)
        flow_lines = ctx.capital_flow(lp_symbol)
        intraday = [
            FlowLine(timestamp=str(fl.timestamp), inflow=Decimal(str(fl.inflow)))
            for fl in flow_lines
        ]

        return MoneyFlow(
            symbol=lp_symbol,
            large_in=Decimal(str(dist.capital_in.large)),
            large_out=Decimal(str(dist.capital_out.large)),
            medium_in=Decimal(str(dist.capital_in.medium)),
            medium_out=Decimal(str(dist.capital_out.medium)),
            small_in=Decimal(str(dist.capital_in.small)),
            small_out=Decimal(str(dist.capital_out.small)),
            intraday=intraday or None,
        )
    except NotImplementedError:
        raise
    except Exception as e:
        raise SourceError(f"Longport flow API error: {e}") from e


def _get_sector_flow(name: str, target_type: TargetType) -> SectorFlow:
    """Get sector/concept money flow from akshare."""
    sector_type = _SECTOR_TYPE_MAP[target_type]

    try:
        df = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type=sector_type)

        if df.empty:
            raise SourceError(f"No {target_type.value} flow data available")

        matched = df[df["名称"].str.contains(name, na=False)]
        if matched.empty:
            raise SourceError(f"{target_type.value.title()} '{name}' not found in flow data")

        row = matched.iloc[0]
        return SectorFlow(
            sector=str(row["名称"]),
            change_pct=Decimal(str(row["今日涨跌幅"])) if row["今日涨跌幅"] is not None else None,
            main_net=(
                Decimal(str(row["今日主力净流入-净额"]))
                if row["今日主力净流入-净额"] is not None
                else None
            ),
        )
    except SourceError:
        raise
    except Exception as e:
        raise SourceError(f"Failed to fetch {target_type.value} flow for '{name}': {e}") from e
