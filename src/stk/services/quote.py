"""Quote facade — all markets via longport, sectors/concepts via akshare."""

from decimal import Decimal

import akshare as ak

from stk.errors import SourceError
from stk.models.common import TargetType
from stk.models.quote import BoardCons, BoardItem, BoardList, ConsItem, Quote


def get_quote(symbol: str, *, target_type: TargetType = TargetType.STOCK) -> Quote:
    """Get real-time quote via longport (stock/index) or akshare (sector/concept)."""
    if target_type in (TargetType.STOCK, TargetType.INDEX):
        from stk.services.longport_quote import get_realtime_quote

        data = get_realtime_quote(symbol)
        return Quote(**data)

    if target_type == TargetType.SECTOR:
        return _get_board_quote(symbol, ak.stock_board_industry_name_em, "sector")

    if target_type == TargetType.CONCEPT:
        return _get_board_quote(symbol, ak.stock_board_concept_name_em, "concept")

    raise NotImplementedError(f"Quote for {target_type.value} not yet implemented")


def _get_board_quote(name: str, fetch_fn, board_type: str) -> Quote:
    """Get sector/concept board quote from akshare."""
    try:
        df = fetch_fn()

        if df.empty:
            raise SourceError(f"No {board_type} board data available")

        # Filter by name (fuzzy match)
        matched = df[df["板块名称"].str.contains(name, na=False)]
        if matched.empty:
            raise SourceError(f"{board_type.title()} '{name}' not found")

        row = matched.iloc[0]
        return Quote(
            symbol=str(row.get("板块代码", name)),
            name=str(row["板块名称"]),
            last=Decimal(str(row["最新价"])) if row["最新价"] is not None else Decimal(0),
            change=(
                Decimal(str(row["涨跌额"]))
                if "涨跌额" in row and row.get("涨跌额") is not None
                else None
            ),
            change_pct=Decimal(str(row["涨跌幅"])) if row["涨跌幅"] is not None else None,
            turnover=Decimal(str(row["总市值"])) if row.get("总市值") is not None else None,
        )
    except SourceError:
        raise
    except Exception as e:
        raise SourceError(f"Failed to fetch {board_type} quote for '{name}': {e}") from e


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

_SKIP_COLS = {"序号", "板块名称", "板块代码", "代码", "名称"}


def _to_decimal(val) -> Decimal | None:
    try:
        s = str(val)
        if s in ("", "-", "nan", "NaN", "None") or val is None:
            return None
        return Decimal(s)
    except Exception:
        return None


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
        metric_cols = [c for c in df.columns if c not in _SKIP_COLS]

        items: list[BoardItem] = []
        for _, row in df.iterrows():
            metrics = {c: _to_decimal(row[c]) for c in metric_cols}
            items.append(
                BoardItem(
                    code=str(row[code_col]),
                    name=str(row[name_col]),
                    metrics=metrics,
                )
            )

        return BoardList(type=type, items=items)
    except SourceError:
        raise
    except Exception as e:
        raise SourceError(f"Failed to fetch {type} board list: {e}") from e


def get_board_cons(name: str, *, type: str = "sector") -> BoardCons:
    """Get constituent stocks of a board (sector/concept)."""
    cfg = _BOARD_API.get(type)
    if not cfg:
        raise SourceError(f"Unknown board type: {type}, use sector/concept")

    try:
        df = getattr(ak, cfg["cons"])(symbol=name)
        if df.empty:
            raise SourceError(f"No constituents for {type} '{name}'")

        metric_cols = [c for c in df.columns if c not in _SKIP_COLS]
        items: list[ConsItem] = []
        for _, row in df.iterrows():
            metrics = {c: _to_decimal(row[c]) for c in metric_cols}
            items.append(
                ConsItem(
                    code=str(row.get("代码", "")),
                    name=str(row.get("名称", "")),
                    metrics=metrics,
                )
            )

        return BoardCons(board=name, type=type, items=items)
    except SourceError:
        raise
    except Exception as e:
        raise SourceError(f"Failed to fetch {type} constituents for '{name}': {e}") from e
