"""Money flow service — individual stock flow via longport."""

from decimal import Decimal

from stk.deps import get_longport_ctx
from stk.errors import SourceError
from stk.models.flow import FlowLine, StockFlow


def get_stock_flow(symbol: str) -> StockFlow:
    """Get individual stock money flow via longport capital distribution."""
    from stk.utils.symbol import to_longport_symbol

    lp_symbol = to_longport_symbol(symbol)

    try:
        ctx = get_longport_ctx()
        dist = ctx.capital_distribution(lp_symbol)
        flow_lines = ctx.capital_flow(lp_symbol)
    except Exception as e:
        raise SourceError(f"Failed to get flow data for {symbol}: {e}") from e

    intraday = [
        FlowLine(timestamp=str(fl.timestamp), inflow=Decimal(str(fl.inflow)))
        for fl in reversed(flow_lines)
    ] or None

    return StockFlow(
        symbol=lp_symbol,
        large_in=Decimal(str(dist.capital_in.large)),
        large_out=Decimal(str(dist.capital_out.large)),
        medium_in=Decimal(str(dist.capital_in.medium)),
        medium_out=Decimal(str(dist.capital_out.medium)),
        small_in=Decimal(str(dist.capital_in.small)),
        small_out=Decimal(str(dist.capital_out.small)),
        intraday=intraday,
    )
