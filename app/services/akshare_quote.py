"""Akshare wrapper for A-share data."""

from app.errors import SourceError


def get_realtime_quote(symbol: str) -> dict:
    """Fetch real-time A-share quote from akshare."""
    try:
        import akshare as ak

        df = ak.stock_zh_a_spot_em()
        row = df[df["代码"] == symbol]
        if row.empty:
            raise SourceError(f"Symbol {symbol} not found in A-share market")
        r = row.iloc[0]
        return {
            "symbol": symbol,
            "name": r.get("名称", ""),
            "last": r.get("最新价"),
            "open": r.get("今开"),
            "high": r.get("最高"),
            "low": r.get("最低"),
            "prev_close": r.get("昨收"),
            "volume": r.get("成交量"),
            "turnover": r.get("成交额"),
        }
    except SourceError:
        raise
    except Exception as e:
        raise SourceError(f"Akshare API error: {e}") from e
