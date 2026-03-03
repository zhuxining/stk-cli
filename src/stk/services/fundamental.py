"""Fundamental data service (financials, valuation, dividends)."""

from decimal import Decimal

from stk.deps import get_longport_ctx
from stk.errors import SourceError
from stk.models.fundamental import Dividend, FinancialReport, Valuation
from stk.services.symbol import to_longport_symbol
from stk.utils.price import r2


def get_financial_report(
    symbol: str,
    *,
    report_type: str = "income",
    period: str = "latest",
) -> FinancialReport:
    """Get financial report. TODO: needs akshare — longport has no report detail API."""
    raise NotImplementedError("Financial report not yet implemented (needs akshare)")


def get_valuation(symbol: str) -> Valuation:
    """Get valuation metrics via longport static_info + quote."""
    try:
        ctx = get_longport_ctx()
        lp_symbol = to_longport_symbol(symbol)

        static = ctx.static_info([lp_symbol])
        if not static:
            raise SourceError(f"No static info for {symbol}")
        info = static[0]

        quotes = ctx.quote([lp_symbol])
        if not quotes:
            raise SourceError(f"No quote data for {symbol}")
        q = quotes[0]

        price = Decimal(str(q.last_done))
        total_shares = info.total_shares
        circulating = info.circulating_shares
        eps = Decimal(str(info.eps_ttm)) if info.eps_ttm else None
        bps = Decimal(str(info.bps)) if info.bps else None

        pe = r2(price / eps) if (eps and eps != 0) else None
        pb = r2(price / bps) if (bps and bps != 0) else None
        market_cap = r2(price * total_shares) if total_shares else None

        return Valuation(
            symbol=lp_symbol,
            pe=pe,
            pb=pb,
            market_cap=market_cap,
            total_shares=total_shares,
            float_shares=circulating,
        )
    except SourceError, NotImplementedError:
        raise
    except Exception as e:
        raise SourceError(f"Longport valuation API error: {e}") from e


def get_dividends(symbol: str) -> list[Dividend]:
    """Get dividend history. TODO: needs akshare — longport has no dividend detail API."""
    raise NotImplementedError("Dividend history not yet implemented (needs akshare)")
