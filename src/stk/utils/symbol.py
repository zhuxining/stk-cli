"""Symbol normalization and data conversion utilities."""

from decimal import Decimal
import re

import pandas as pd

# ---------------------------------------------------------------------------
# Symbol normalization — user input → longport/akshare/eastmoney format
# ---------------------------------------------------------------------------


def to_longport_symbol(symbol: str) -> str:
    """
    Convert user input to longport symbol format.

    - 700.HK / AAPL.US / HSI.HK / 000001.SH → pass through
    - .DJI / .IXIC / .SPX → pass through (US index)
    - 600519 / 688001 → 600519.SH / 688001.SH (上交所主板/科创板)
    - 000001 / 002001 / 300001 → 000001.SZ / 002001.SZ / 300001.SZ (深交所)
    - 800001 / 830001 → 800001.BJ (北交所) **新增**
    """
    # Already has suffix (.HK, .US, .SH, .SZ, .BJ) or US index prefix (.)
    if re.search(r"\.\w+$", symbol) or symbol.startswith("."):
        return symbol

    # Pure 6-digit A-share code
    if re.fullmatch(r"\d{6}", symbol):
        # 北交所 (8 开头)
        if symbol.startswith("8"):
            return f"{symbol}.BJ"
        # 上交所 (6 开头，含科创板 688)
        if symbol.startswith("6"):
            return f"{symbol}.SH"
        # 深交所 (0/2/3 开头)
        return f"{symbol}.SZ"

    return symbol


def to_em_symbol(symbol: str) -> str:
    """Convert to EastMoney format: 600519 → SH600519, 000001 → SZ000001."""
    lp = to_longport_symbol(symbol)
    if "." not in lp:
        return lp
    code, market = lp.split(".", 1)
    return f"{market}{code}"


def to_ak_market(symbol: str) -> tuple[str, str]:
    """
    Convert symbol to akshare (stock, market) format.

    Returns (code, market) where market is 'sh' or 'sz'.
    Raises ValueError for non-A-share symbols.
    """
    lp = to_longport_symbol(symbol)
    if not lp.endswith((".SH", ".SZ")):
        raise ValueError(f"to_ak_market only supports A-share symbols (.SH/.SZ), got: {lp}")
    code, market = lp.split(".", 1)
    return code, market.lower()


def is_hk(symbol: str) -> bool:
    """Check if symbol is a HK stock."""
    return to_longport_symbol(symbol).endswith(".HK")


def to_hk_code(symbol: str) -> str:
    """Extract HK code with zero padding: 700.HK → 00700, 3900.HK → 03900."""
    lp = to_longport_symbol(symbol)
    code = lp.split(".")[0]
    return code.zfill(5)


# ---------------------------------------------------------------------------
# DataFrame conversion helpers for akshare data
# ---------------------------------------------------------------------------


def to_decimal(val) -> Decimal | None:
    """
    Safely convert a value to Decimal, returning None for invalid inputs.

    Handles: None, "", "-", "nan", "NaN", and non-numeric strings.
    """
    try:
        s = str(val)
        if s in ("", "-", "nan", "NaN", "None") or val is None:
            return None
        return Decimal(s)
    except Exception:
        return None


def to_metrics(
    row: pd.Series,
    columns: list[str],
    skip_cols: set[str] | None = None,
) -> dict[str, Decimal | None]:
    """
    Convert a DataFrame row to a metrics dict, skipping non-metric columns.

    Args:
        row: pandas Series (a DataFrame row)
        columns: list of column names to process
        skip_cols: set of column names to skip (default: common non-metric cols)

    """
    if skip_cols is None:
        skip_cols = {"序号", "代码", "简称", "名称", "板块名称", "板块代码", "股票代码", "股票简称"}

    metrics: dict[str, Decimal | None] = {}
    for col in columns:
        if col in skip_cols:
            continue
        metrics[col] = to_decimal(row[col])
    return metrics
