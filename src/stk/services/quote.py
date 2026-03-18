"""Quote service — real-time quotes via longport."""

from decimal import Decimal

from stk.errors import SourceError
from stk.models.common import TargetType
from stk.models.quote import Quote
from stk.store.cache import cached
from stk.utils.df import to_decimal


def get_quote(symbol: str, *, target_type: TargetType = TargetType.STOCK) -> Quote:
    """Get real-time quote via longport (stock/index) or akshare (sector/concept)."""
    if target_type in (TargetType.STOCK, TargetType.INDEX):
        from stk.services.longport_quote import get_realtime_quote

        return get_realtime_quote(symbol)

    if target_type == TargetType.SECTOR:
        return _get_board_quote(symbol, board_type="sector")

    if target_type == TargetType.CONCEPT:
        return _get_board_quote(symbol, board_type="concept")

    raise NotImplementedError(f"Quote for {target_type} not yet implemented")


@cached(ttl=300)
def _get_board_quote(name: str, board_type: str) -> Quote:
    """Get sector/concept board quote from akshare."""
    import akshare as ak

    try:
        if board_type == "sector":
            df = ak.stock_board_industry_name_em()
        else:
            df = ak.stock_board_concept_name_em()

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
            last=to_decimal(row["最新价"]) or Decimal(0),
            change=to_decimal(row.get("涨跌额")),
            change_pct=to_decimal(row["涨跌幅"]),
            turnover=to_decimal(row.get("总市值")),
        )
    except SourceError:
        raise
    except Exception as e:
        raise SourceError(f"Failed to fetch {board_type} quote for '{name}': {e}") from e
