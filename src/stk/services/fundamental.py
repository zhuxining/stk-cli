"""Fundamental data service (industry comparison, valuation)."""

from decimal import Decimal

import akshare as ak

from stk.deps import get_longport_ctx
from stk.errors import SourceError
from stk.models.fundamental import (
    CompanyMetric,
    CompanyProfile,
    IndustryComparison,
    Valuation,
)
from stk.services.symbol import to_longport_symbol
from stk.utils.price import r2

_A_CATEGORY_API = {
    "growth": "stock_zh_growth_comparison_em",
    "valuation": "stock_zh_valuation_comparison_em",
    "dupont": "stock_zh_dupont_comparison_em",
}

_HK_CATEGORY_API = {
    "growth": "stock_hk_growth_comparison_em",
    "valuation": "stock_hk_valuation_comparison_em",
}

# Columns to skip when building metrics dict
_SKIP_COLS = {"排名", "代码", "简称"}
# Also skip ranking columns (contain "排名")
_SKIP_SUFFIX = "排名"


def _to_em_symbol(symbol: str) -> str:
    """Convert to EastMoney format: 600519 → SH600519, 000001 → SZ000001."""
    lp = to_longport_symbol(symbol)
    if "." not in lp:
        return lp
    code, market = lp.split(".", 1)
    return f"{market}{code}"


def _is_hk(symbol: str) -> bool:
    """Check if symbol is a HK stock."""
    return to_longport_symbol(symbol).endswith(".HK")


def _to_hk_code(symbol: str) -> str:
    """Extract HK code: 700.HK → 00700, 3900.HK → 03900."""
    lp = to_longport_symbol(symbol)
    code = lp.split(".")[0]
    return code.zfill(5)


def get_comparison(symbol: str, *, category: str = "growth") -> IndustryComparison:
    """Get industry comparison data from akshare (A-share and HK)."""
    lp_symbol = to_longport_symbol(symbol)
    hk = _is_hk(symbol)

    category_map = _HK_CATEGORY_API if hk else _A_CATEGORY_API
    api_name = category_map.get(category)
    if not api_name:
        valid = "/".join(category_map.keys())
        raise SourceError(f"Unknown category: {category}, use {valid}")

    em_symbol = _to_hk_code(symbol) if hk else _to_em_symbol(symbol)

    try:
        api_fn = getattr(ak, api_name)
        df = api_fn(symbol=em_symbol)

        if df.empty:
            raise SourceError(f"No {category} comparison data for {symbol}")

        companies: list[CompanyMetric] = []
        for _, row in df.iterrows():
            code = str(row.get("代码", row.get("简称", "")))
            name = str(row.get("简称", code))
            metrics: dict[str, Decimal | None] = {}
            for col in df.columns:
                if col in _SKIP_COLS or col.endswith(_SKIP_SUFFIX):
                    continue
                val = row[col]
                try:
                    if val is not None and str(val) not in ("NaN", "nan", "", "-"):
                        metrics[col] = Decimal(str(val))
                    else:
                        metrics[col] = None
                except Exception:
                    metrics[col] = None
            companies.append(CompanyMetric(code=code, name=name, metrics=metrics))

        return IndustryComparison(
            symbol=lp_symbol,
            category=category,
            companies=companies,
        )
    except SourceError:
        raise
    except Exception as e:
        raise SourceError(f"Failed to fetch {category} comparison for {symbol}: {e}") from e


def get_valuation(symbol: str) -> Valuation:
    """Get valuation metrics via longport static_info + quote."""
    try:
        ctx = get_longport_ctx()
        lp_symbol = to_longport_symbol(symbol)

        static = ctx.static_info([lp_symbol])
        if not static:
            raise SourceError(f"No static info for {symbol}")
        info = static[0]

        quotes = ctx.quote([lp_symbol])
        if not quotes:
            raise SourceError(f"No quote data for {symbol}")
        q = quotes[0]

        price = Decimal(str(q.last_done))
        total_shares = info.total_shares
        circulating = info.circulating_shares
        eps = Decimal(str(info.eps_ttm)) if info.eps_ttm else None
        bps = Decimal(str(info.bps)) if info.bps else None

        pe = r2(price / eps) if (eps and eps != 0) else None
        pb = r2(price / bps) if (bps and bps != 0) else None
        market_cap = r2(price * total_shares) if total_shares else None

        return Valuation(
            symbol=lp_symbol,
            pe=pe,
            pb=pb,
            market_cap=market_cap,
            total_shares=total_shares,
            float_shares=circulating,
        )
    except SourceError:
        raise
    except NotImplementedError:
        raise
    except Exception as e:
        raise SourceError(f"Longport valuation API error: {e}") from e


def get_profile(symbol: str) -> CompanyProfile:
    """Get company main business profile from akshare (A-share)."""
    lp_symbol = to_longport_symbol(symbol)
    ak_code = lp_symbol.split(".")[0] if "." in lp_symbol else lp_symbol

    try:
        df = ak.stock_zyjs_ths(symbol=ak_code)

        if df.empty:
            raise SourceError(f"No profile data for {symbol}")

        row = df.iloc[0]
        return CompanyProfile(
            symbol=lp_symbol,
            main_business=str(row.get("主营业务", "")),
            product_type=str(row.get("产品类型", "")),
            product_name=str(row.get("产品名称", "")),
            business_scope=str(row.get("经营范围", "")),
        )
    except SourceError:
        raise
    except Exception as e:
        raise SourceError(f"Failed to fetch profile for {symbol}: {e}") from e
