"""Symbol normalization — user input → longport format."""

import re


def to_longport_symbol(symbol: str) -> str:
    """Convert user input to longport symbol format.

    - 700.HK / AAPL.US / HSI.HK / 000001.SH → pass through
    - .DJI / .IXIC / .SPX → pass through (US index)
    - 600519 → 600519.SH
    - 000001 → 000001.SZ
    - 300750 → 300750.SZ
    """
    # Already has suffix (.HK, .US, .SH, .SZ) or US index prefix (.)
    if re.search(r"\.\w+$", symbol) or symbol.startswith("."):
        return symbol

    # Pure 6-digit A-share code
    if re.fullmatch(r"\d{6}", symbol):
        return f"{symbol}.SH" if symbol.startswith("6") else f"{symbol}.SZ"

    return symbol
