"""Money flow service — individual stock and flow rankings."""

from decimal import Decimal

import akshare as ak
import pandas as pd

from stk.deps import get_longport_ctx
from stk.errors import SourceError
from stk.models.flow import FlowLine, FlowRank, FlowRankItem, StockFlow
from stk.utils.symbol import to_ak_market, to_decimal, to_metrics

_SKIP_FLOW_COLS = {"序号", "代码", "简称", "名称"}


def _df_to_flow_items(df: pd.DataFrame) -> list[FlowRankItem]:
    """Convert a DataFrame to a list of FlowRankItem."""
    cols = df.columns.tolist()
    items: list[FlowRankItem] = []
    for _, row in df.iterrows():
        code = str(row.get("代码", row.get("名称", "")))
        name = str(row.get("简称", row.get("名称", code)))
        items.append(
            FlowRankItem(
                code=code,
                name=name,
                metrics=to_metrics(row, cols, _SKIP_FLOW_COLS),
            )
        )
    return items


# ---------------------------------------------------------------------------
# 1. get_stock_flow — 个股资金流 (longport realtime + akshare history)
# ---------------------------------------------------------------------------


def get_stock_flow(symbol: str) -> StockFlow:
    """Get individual stock money flow — realtime + recent history."""
    from stk.utils.symbol import to_longport_symbol

    lp_symbol = to_longport_symbol(symbol)
    result = StockFlow(symbol=lp_symbol)

    # Longport realtime distribution
    try:
        ctx = get_longport_ctx()
        dist = ctx.capital_distribution(lp_symbol)
        flow_lines = ctx.capital_flow(lp_symbol)
        result.large_in = Decimal(str(dist.capital_in.large))
        result.large_out = Decimal(str(dist.capital_out.large))
        result.medium_in = Decimal(str(dist.capital_in.medium))
        result.medium_out = Decimal(str(dist.capital_out.medium))
        result.small_in = Decimal(str(dist.capital_in.small))
        result.small_out = Decimal(str(dist.capital_out.small))
        result.intraday = [
            FlowLine(timestamp=str(fl.timestamp), inflow=Decimal(str(fl.inflow)))
            for fl in flow_lines
        ] or None
    except Exception:
        pass  # longport may not support all markets

    # Akshare history (A-share only)
    if lp_symbol.endswith((".SH", ".SZ")):
        try:
            code, market = to_ak_market(symbol)
            df = ak.stock_individual_fund_flow(stock=code, market=market)
            if not df.empty:
                cols = df.columns.tolist()
                history = []
                for _, row in df.head(10).iterrows():
                    day: dict[str, Decimal | None] = {}
                    for col in cols:
                        val = row[col]
                        try:
                            s = str(val)
                            if s in ("", "-", "nan", "NaN", "None"):
                                day[col] = None
                            else:
                                day[col] = Decimal(s)
                        except Exception:
                            day[col] = None
                    history.append(day)
                result.history = history
        except Exception:
            pass  # akshare history is supplementary

    if not result.large_in and not result.history:
        raise SourceError(f"No flow data available for {symbol}")

    return result


# ---------------------------------------------------------------------------
# 2. get_flow_rank — 资金流排名
# ---------------------------------------------------------------------------

_SECTOR_TYPE_MAP = {
    "sector": "行业资金流",
    "concept": "概念资金流",
}


def get_flow_rank(
    *,
    scope: str = "stock",
    period: str = "今日",
    market: str = "全部股票",
) -> FlowRank:
    """
    Get fund flow ranking.

    scope: stock / main / sector / concept
    period: 今日 / 3 日 / 5 日 / 10 日 (not all periods valid for all scopes)
    market: for main scope only — 全部股票 / 沪深 A 股 / etc.
    """
    try:
        if scope == "stock":
            df = ak.stock_individual_fund_flow_rank(indicator=period)
        elif scope == "main":
            df = ak.stock_main_fund_flow(symbol=market)
        elif scope in ("sector", "concept"):
            sector_type = _SECTOR_TYPE_MAP[scope]
            df = ak.stock_sector_fund_flow_rank(
                indicator=period,
                sector_type=sector_type,
            )
        else:
            raise SourceError(f"Unknown scope: {scope}, use stock/main/sector/concept")

        if df.empty:
            raise SourceError(f"No {scope} flow rank data")

        return FlowRank(
            scope=scope,
            period=period,
            items=_df_to_flow_items(df),
        )
    except SourceError:
        raise
    except Exception as e:
        raise SourceError(f"Failed to fetch {scope} flow rank: {e}") from e
