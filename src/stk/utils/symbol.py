"""Symbol normalization utilities."""

import re

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
    - 800001 / 830001 / 430001 / 920001 → .BJ (北交所)
    """
    # Already has suffix (.HK, .US, .SH, .SZ, .BJ) or US index prefix (.)
    if re.search(r"\.\w+$", symbol) or symbol.startswith("."):
        return symbol

    # Pure 6-digit A-share code
    if re.fullmatch(r"\d{6}", symbol):
        # 北交所 (4/8/9 开头)
        if symbol.startswith(("4", "8", "9")):
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
# Symbol helpers
# ---------------------------------------------------------------------------


def extract_code(symbol: str) -> str:
    """Strip market suffix: '600519.SH' → '600519', '700.HK' → '700'."""
    return symbol.split(".")[0] if "." in symbol else symbol


def is_etf(symbol: str) -> bool:
    """Check if symbol is an A-share ETF (SH:5xxxxx / SZ:159xxx)."""
    lp = to_longport_symbol(symbol)
    code = extract_code(lp)
    if lp.endswith(".SH") and code.startswith("5"):
        return True
    return bool(lp.endswith(".SZ") and code.startswith("159"))
