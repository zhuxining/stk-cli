"""Board service — sector/concept board data and money flow."""

import akshare as ak

from stk.errors import SourceError
from stk.models.flow import SectorFlowDay, SectorFlowDetail, SectorFlowHist
from stk.models.quote import BoardCons, BoardItem, BoardList, ConsItem
from stk.services.flow import _SKIP_FLOW_COLS, _df_to_flow_items
from stk.store.cache import cached
from stk.utils.df import to_decimal, to_metrics

# ---------------------------------------------------------------------------
# Board listing and constituents
# ---------------------------------------------------------------------------

_BOARD_API = {
    "sector": {
        "list": "stock_board_industry_name_em",
        "cons": "stock_board_industry_cons_em",
        "name_col": "板块名称",
        "code_col": "板块代码",
    },
    "concept": {
        "list": "stock_board_concept_name_em",
        "cons": "stock_board_concept_cons_em",
        "name_col": "板块名称",
        "code_col": "板块代码",
    },
}

_SKIP_BOARD_COLS = {"序号", "板块名称", "板块代码", "代码", "名称"}


@cached(ttl=14400, disk=True)
def get_board_list(*, type: str = "sector") -> BoardList:
    """Get board (sector/concept) listing with quotes."""
    cfg = _BOARD_API.get(type)
    if not cfg:
        raise SourceError(f"Unknown board type: {type}, use sector/concept")

    try:
        df = getattr(ak, cfg["list"])()
        if df.empty:
            raise SourceError(f"No {type} board data")

        name_col = cfg["name_col"]
        code_col = cfg["code_col"]
        metric_cols = [c for c in df.columns if c not in _SKIP_BOARD_COLS]

        items: list[BoardItem] = []
        for _, row in df.iterrows():
            items.append(
                BoardItem(
                    code=str(row[code_col]),
                    name=str(row[name_col]),
                    metrics=to_metrics(row, metric_cols),
                )
            )

        return BoardList(type=type, items=items)
    except SourceError:
        raise
    except Exception as e:
        raise SourceError(f"Failed to fetch {type} board list: {e}") from e


@cached(ttl=14400, disk=True)
def get_board_cons(name: str, *, type: str = "sector") -> BoardCons:
    """Get constituent stocks of a board (sector/concept)."""
    cfg = _BOARD_API.get(type)
    if not cfg:
        raise SourceError(f"Unknown board type: {type}, use sector/concept")

    try:
        df = getattr(ak, cfg["cons"])(symbol=name)
        if df.empty:
            raise SourceError(f"No constituents for {type} '{name}'")

        metric_cols = [c for c in df.columns if c not in _SKIP_BOARD_COLS]

        items: list[ConsItem] = []
        for _, row in df.iterrows():
            items.append(
                ConsItem(
                    code=str(row.get("代码", "")),
                    name=str(row.get("名称", "")),
                    metrics=to_metrics(row, metric_cols),
                )
            )

        return BoardCons(board=name, type=type, items=items)
    except SourceError:
        raise
    except Exception as e:
        raise SourceError(f"Failed to fetch {type} constituents for '{name}': {e}") from e


# ---------------------------------------------------------------------------
# Sector/concept money flow
# ---------------------------------------------------------------------------


@cached(ttl=3600)
def get_sector_flow_hist(name: str, *, type: str = "sector") -> SectorFlowHist:
    """Get historical fund flow for a sector or concept."""
    try:
        if type == "sector":
            df = ak.stock_sector_fund_flow_hist(symbol=name)
        elif type == "concept":
            df = ak.stock_concept_fund_flow_hist(symbol=name)
        else:
            raise SourceError(f"Unknown type: {type}, use sector/concept")

        if df.empty:
            raise SourceError(f"No history flow data for '{name}'")

        cols = df.columns.tolist()
        date_col = cols[0]
        days: list[SectorFlowDay] = []
        for _, row in df.iterrows():
            days.append(
                SectorFlowDay(
                    date=str(row[date_col]),
                    metrics=to_metrics(row, cols[1:], _SKIP_FLOW_COLS),
                )
            )

        return SectorFlowHist(name=name, type=type, days=days)
    except SourceError:
        raise
    except Exception as e:
        raise SourceError(f"Failed to fetch {type} flow history for '{name}': {e}") from e


@cached(ttl=300)
def get_sector_flow_detail(name: str, *, period: str = "今日") -> SectorFlowDetail:
    """Get individual stocks' fund flow within a sector."""
    try:
        df = ak.stock_sector_fund_flow_summary(symbol=name, indicator=period)
        if df.empty:
            raise SourceError(f"No detail flow data for '{name}'")

        return SectorFlowDetail(
            sector=name,
            period=period,
            items=_df_to_flow_items(df),
        )
    except SourceError:
        raise
    except Exception as e:
        raise SourceError(f"Failed to fetch sector detail flow for '{name}': {e}") from e
