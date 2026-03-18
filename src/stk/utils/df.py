"""DataFrame and numeric conversion helpers for akshare data."""

from decimal import Decimal

import pandas as pd


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
