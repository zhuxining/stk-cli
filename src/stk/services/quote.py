"""Quote facade — all markets via longport, sectors/concepts via akshare."""

from decimal import Decimal

import akshare as ak

from stk.errors import SourceError
from stk.models.common import TargetType
from stk.models.quote import Quote


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
