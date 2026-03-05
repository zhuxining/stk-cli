"""Tests for symbol normalization and data conversion."""

import pytest

from stk.utils.symbol import (
    is_hk,
    to_ak_market,
    to_em_symbol,
    to_hk_code,
    to_longport_symbol,
)


@pytest.mark.parametrize(
    ("input_symbol", "expected"),
    [
        # Pass-through: already has suffix
        ("700.HK", "700.HK"),
        ("AAPL.US", "AAPL.US"),
        ("HSI.HK", "HSI.HK"),
        ("000001.SH", "000001.SH"),
        ("399001.SZ", "399001.SZ"),
        # Pass-through: US index with dot prefix
        (".DJI", ".DJI"),
        (".IXIC", ".IXIC"),
        (".SPX", ".SPX"),
        # A-share: 6xx → .SH (主板)
        ("600519", "600519.SH"),
        ("601318", "601318.SH"),
        # A-share: 688xxx → .SH (科创板)
        ("688001", "688001.SH"),
        ("688888", "688888.SH"),
        # A-share: 0xx/2xx/3xx → .SZ (深交所)
        ("000001", "000001.SZ"),
        ("000858", "000858.SZ"),
        ("002001", "002001.SZ"),
        ("300750", "300750.SZ"),
        # A-share: 8xxxxx → .BJ (北交所) **新增**
        ("800001", "800001.BJ"),
        ("830001", "830001.BJ"),
        # Other: pass through
        ("TSLA", "TSLA"),
    ],
)
def test_to_longport_symbol(input_symbol, expected):
    """Test symbol normalization to Longport format."""
    assert to_longport_symbol(input_symbol) == expected


@pytest.mark.parametrize(
    ("input_symbol", "expected"),
    [
        ("600519", "SH600519"),
        ("000001", "SZ000001"),
        ("688001", "SH688001"),
        ("300750", "SZ300750"),
        ("700.HK", "HK700"),  # to_em_symbol doesn't zero-pad HK codes
    ],
)
def test_to_em_symbol(input_symbol, expected):
    """Test conversion to EastMoney format."""
    assert to_em_symbol(input_symbol) == expected


@pytest.mark.parametrize(
    ("input_symbol", "expected"),
    [
        ("600519", ("600519", "sh")),
        ("000001", ("000001", "sz")),
        ("688001", ("688001", "sh")),
    ],
)
def test_to_ak_market(input_symbol, expected):
    """Test conversion to akshare (code, market) format."""
    assert to_ak_market(input_symbol) == expected


@pytest.mark.parametrize("input_symbol", ["700.HK", "AAPL.US", ".DJI", "TSLA"])
def test_to_ak_market_rejects_non_a_share(input_symbol):
    """Test to_ak_market raises ValueError for non-A-share symbols."""
    with pytest.raises(ValueError, match="only supports A-share"):
        to_ak_market(input_symbol)


@pytest.mark.parametrize(
    ("input_symbol", "expected"),
    [
        ("700.HK", True),
        ("00700.HK", True),
        ("600519", False),
        ("AAPL.US", False),
    ],
)
def test_is_hk(input_symbol, expected):
    """Test HK stock detection."""
    assert is_hk(input_symbol) == expected


@pytest.mark.parametrize(
    ("input_symbol", "expected"),
    [
        ("700.HK", "00700"),
        ("00700.HK", "00700"),
        ("3900.HK", "03900"),
        ("1234.HK", "01234"),
    ],
)
def test_to_hk_code(input_symbol, expected):
    """Test HK code extraction with zero padding."""
    assert to_hk_code(input_symbol) == expected
