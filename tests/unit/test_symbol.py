"""Tests for symbol normalization."""

import pytest

from stk.services.symbol import to_longport_symbol


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
        # A-share: 6xx → .SH
        ("600519", "600519.SH"),
        ("601318", "601318.SH"),
        # A-share: 0xx/3xx → .SZ
        ("000001", "000001.SZ"),
        ("000858", "000858.SZ"),
        ("300750", "300750.SZ"),
        # Other: pass through
        ("TSLA", "TSLA"),
    ],
)
def test_to_longport_symbol(input_symbol, expected):
    """Test symbol normalization to Longport format."""
    assert to_longport_symbol(input_symbol) == expected
