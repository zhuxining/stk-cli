"""Fundamental data service (industry comparison, valuation)."""

from decimal import Decimal

import akshare as ak
from longport.openapi import CalcIndex

from stk.deps import get_longport_ctx
from stk.errors import SourceError
from stk.models.fundamental import (
    CompanyMetric,
    CompanyProfile,
    IndustryComparison,
    Valuation,
)
from stk.store.cache import cached
from stk.utils.price import r2
from stk.utils.symbol import extract_code, is_hk, to_em_symbol, to_hk_code, to_longport_symbol

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


@cached(ttl=86400, disk=True)
def get_comparison(symbol: str, *, category: str = "growth") -> IndustryComparison:
    """Get industry comparison data from akshare (A-share and HK)."""
    lp_symbol = to_longport_symbol(symbol)
    hk = is_hk(symbol)

    category_map = _HK_CATEGORY_API if hk else _A_CATEGORY_API
    api_name = category_map.get(category)
    if not api_name:
        valid = "/".join(category_map.keys())
        raise SourceError(f"Unknown category: {category}, use {valid}")

    em_symbol = to_hk_code(symbol) if hk else to_em_symbol(symbol)

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


_VALUATION_INDEXES = [
    CalcIndex.LastDone,
    CalcIndex.ChangeValue,
    CalcIndex.ChangeRate,
    CalcIndex.Volume,
    CalcIndex.Turnover,
    CalcIndex.YtdChangeRate,
    CalcIndex.TurnoverRate,
    CalcIndex.TotalMarketValue,
    CalcIndex.CapitalFlow,
    CalcIndex.Amplitude,
    CalcIndex.VolumeRatio,
    CalcIndex.PeTtmRatio,
    CalcIndex.PbRatio,
    CalcIndex.DividendRatioTtm,
    CalcIndex.FiveDayChangeRate,
    CalcIndex.TenDayChangeRate,
    CalcIndex.HalfYearChangeRate,
    CalcIndex.FiveMinutesChangeRate,
]

# Mapping: (longport attr name, model field name, converter)
# Decimal fields use _d, int fields use _i, str fields use _s
_DECIMAL_FIELDS = [
    ("last_done", "last_done"),
    ("change_value", "change_value"),
    ("change_rate", "change_rate"),
    ("turnover", "turnover"),
    ("ytd_change_rate", "ytd_change_rate"),
    ("turnover_rate", "turnover_rate"),
    ("total_market_value", "total_market_value"),
    ("capital_flow", "capital_flow"),
    ("amplitude", "amplitude"),
    ("volume_ratio", "volume_ratio"),
    ("pe_ttm_ratio", "pe_ttm_ratio"),
    ("pb_ratio", "pb_ratio"),
    ("dividend_ratio_ttm", "dividend_ratio_ttm"),
    ("five_day_change_rate", "five_day_change_rate"),
    ("ten_day_change_rate", "ten_day_change_rate"),
    ("half_year_change_rate", "half_year_change_rate"),
    ("five_minutes_change_rate", "five_minutes_change_rate"),
]

_INT_FIELDS = [
    ("volume", "volume"),
]


def _to_decimal(val: object) -> Decimal | None:
    if val is None:
        return None
    s = str(val)
    if s in ("", "nan", "NaN", "0"):
        return None
    return r2(Decimal(s))


def _build_valuation(r, lp_symbol: str) -> Valuation:
    """Build Valuation model from a single longport calc_indexes result."""
    data: dict[str, str | Decimal | int | None] = {"symbol": lp_symbol}
    for attr, field in _DECIMAL_FIELDS:
        data[field] = _to_decimal(getattr(r, attr, None))
    for attr, field in _INT_FIELDS:
        val = getattr(r, attr, None)
        data[field] = int(val) if val else None
    return Valuation(**data)  # type: ignore[arg-type]


def get_valuations(symbols: list[str]) -> list[Valuation]:
    """Get valuation metrics for multiple symbols in a single API call."""
    try:
        ctx = get_longport_ctx()
        lp_symbols = [to_longport_symbol(s) for s in symbols]

        results = ctx.calc_indexes(lp_symbols, _VALUATION_INDEXES)
        if not results:
            raise SourceError(f"No valuation data for {symbols}")

        return [_build_valuation(r, lp_symbols[i]) for i, r in enumerate(results)]
    except SourceError:
        raise
    except Exception as e:
        raise SourceError(f"Longport valuation API error: {e}") from e


def get_valuation(symbol: str) -> Valuation:
    """Get valuation metrics for a single symbol."""
    return get_valuations([symbol])[0]


@cached(ttl=604800, disk=True)
def get_profile(symbol: str) -> CompanyProfile:
    """Get company main business profile from akshare (A-share)."""
    lp_symbol = to_longport_symbol(symbol)
    ak_code = extract_code(lp_symbol)

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
