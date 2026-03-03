"""Money flow service via longport."""

from decimal import Decimal

from stk.deps import get_longport_ctx
from stk.errors import SourceError
from stk.models.common import TargetType
from stk.models.flow import FlowLine, MoneyFlow, SectorFlow
from stk.services.symbol import to_longport_symbol


def get_flow(
    symbol: str,
    *,
    target_type: TargetType = TargetType.STOCK,
) -> MoneyFlow | SectorFlow:
    """Get money flow data from longport."""
    if target_type != TargetType.STOCK:
        raise NotImplementedError(
            f"Flow for {target_type.value} not yet implemented (needs akshare)"
        )

    try:
        ctx = get_longport_ctx()
        lp_symbol = to_longport_symbol(symbol)

        # Capital distribution (large/medium/small order breakdown)
        dist = ctx.capital_distribution(lp_symbol)

        # Intraday capital flow (minute-level)
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
            intraday=intraday if intraday else None,
        )
    except NotImplementedError:
        raise
    except Exception as e:
        raise SourceError(f"Longport flow API error: {e}") from e
