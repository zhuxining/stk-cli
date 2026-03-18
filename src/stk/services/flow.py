"""Money flow service — individual stock and flow rankings."""

from decimal import Decimal

import akshare as ak
from loguru import logger
import pandas as pd

from stk.deps import get_longport_ctx
from stk.errors import SourceError
from stk.models.flow import FlowLine, FlowRank, FlowRankItem, StockFlow
from stk.store.cache import cached
from stk.utils.df import to_metrics

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
# 1. get_stock_flow — 个股资金流 (longport capital_distribution + capital_flow)
# ---------------------------------------------------------------------------


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
        FlowLine(timestamp=str(fl.timestamp), inflow=Decimal(str(fl.inflow))) for fl in flow_lines
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


# ---------------------------------------------------------------------------
# 2. get_flow_rank — 资金流排名
# ---------------------------------------------------------------------------

_SECTOR_TYPE_MAP = {
    "sector": "行业资金流",
    "concept": "概念资金流",
}


@cached(ttl=300)
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
