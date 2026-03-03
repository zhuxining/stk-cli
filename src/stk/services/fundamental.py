"""Fundamental data service (financials, valuation, dividends)."""

from stk.models.fundamental import Dividend, FinancialReport, Valuation


def get_financial_report(
    symbol: str,
    *,
    report_type: str = "income",
    period: str = "latest",
) -> FinancialReport:
    """Get financial report."""
    # TODO: implement akshare financial data
    raise NotImplementedError("Financial report service not yet implemented")


def get_valuation(symbol: str) -> Valuation:
    """Get valuation metrics."""
    # TODO: implement valuation data
    raise NotImplementedError("Valuation service not yet implemented")


def get_dividends(symbol: str) -> list[Dividend]:
    """Get dividend history."""
    # TODO: implement dividend data
    raise NotImplementedError("Dividend service not yet implemented")
