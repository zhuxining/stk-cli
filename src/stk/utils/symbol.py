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
    - 515220 → 515220.SH (上交所 ETF, 5xxxxx)
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
        # 上交所 (5 开头 ETF, 6 开头含科创板 688)
        if symbol.startswith(("5", "6")):
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


def from_em_symbol(em_symbol: str) -> str:
    """Convert EastMoney format back to longport: SH600519 → 600519.SH, SZ000001 → 000001.SZ."""
    if len(em_symbol) < 3:
        return em_symbol
    market = em_symbol[:2]
    code = em_symbol[2:]
    if market in ("SH", "SZ"):
        return f"{code}.{market}"
    return em_symbol


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


def expand_symbols(symbols: list[str]) -> list[str]:
    """展开逗号分隔的 symbol 列表，兼容空格和逗号两种分隔方式。

    e.g. ['002218,600207', '688552'] → ['002218', '600207', '688552']
    """
    result = []
    for s in symbols:
        result.extend(x.strip() for x in s.split(",") if x.strip())
    return result


def extract_code(symbol: str) -> str:
    """Strip market suffix: '600519.SH' → '600519', '700.HK' → '700'."""
    return symbol.split(".")[0] if "." in symbol else symbol


# ---------------------------------------------------------------------------
# THS (同花顺) symbol conversion
# ---------------------------------------------------------------------------

# A-share codes that need different market suffix in THS
# 科创板: 688xxx → .KC (THS market code 18)
# 创业板: 300xxx/301xxx → .CYB (THS market code 38)
_KC_PREFIXES = ("688",)
_CY_PREFIXES = ("300", "301")

# Longport-supported market suffixes; anything else (indices, funds, bonds, futures...)
# is dropped during THS→longport sync to avoid polluting batch API calls.
_LONGPORT_MARKETS = frozenset({"SH", "SZ", "BJ", "HK", "US"})


def to_ths_symbol(longport_symbol: str) -> str:
    """Convert longport symbol to THS format (CODE.MARKET).

    THS market abbrs (from ths-favorite constant.py): SH/SZ/KC/CYB/BJ/HK/US.
    Note: 创业板 is 'CYB', NOT 'CY'.

    600519.SH → 600519.SH
    688001.SH → 688001.KC  (科创板)
    300001.SZ → 300001.CYB (创业板)
    00700.HK  → 00700.HK
    AAPL.US   → AAPL.US
    """
    lp = to_longport_symbol(longport_symbol)
    if "." not in lp:
        return lp
    code, market = lp.split(".", 1)
    if market == "SH" and code.startswith(_KC_PREFIXES):
        return f"{code}.KC"
    if market == "SZ" and code.startswith(_CY_PREFIXES):
        return f"{code}.CYB"
    return lp


def from_ths_symbol(ths_symbol: str) -> str:
    """Convert THS symbol back to longport format.

    THS market abbrs (from ths-favorite constant.py): SH/SZ/KC/CYB/SHETF/SZETF/BJ/HK/US.
    ETF abbrs (SHETF/SZETF) map back to the exchange suffix (.SH/.SZ).

    600519.SH   → 600519.SH
    688001.KC   → 688001.SH
    300001.CYB  → 300001.SZ
    510300.SHETF → 510300.SH
    159915.SZETF → 159915.SZ
    """
    if "." not in ths_symbol:
        return ths_symbol
    code, market = ths_symbol.split(".", 1)
    if market == "KC":
        return f"{code}.SH"
    if market in ("CY", "CYB"):
        return f"{code}.SZ"
    if market in ("SHETF", "SZETF", "ST"):
        # ETF/ST carry no market info in the suffix; infer from A-share code rules.
        return to_longport_symbol(code)
    return ths_symbol


def is_longport_symbol(symbol: str) -> bool:
    """Check whether a symbol has a longport-supported market suffix.

    Longport supports .SH/.SZ/.BJ/.HK/.US.  Used to filter THS-only assets
    (indices, funds, bonds, futures) out of sync batches.
    """
    lp = to_longport_symbol(symbol)
    return "." in lp and lp.split(".", 1)[1] in _LONGPORT_MARKETS


def is_etf(symbol: str) -> bool:
    """Check if symbol is an A-share ETF (SH:5xxxxx / SZ:159xxx)."""
    lp = to_longport_symbol(symbol)
    code = extract_code(lp)
    if lp.endswith(".SH") and code.startswith("5"):
        return True
    return bool(lp.endswith(".SZ") and code.startswith("159"))
