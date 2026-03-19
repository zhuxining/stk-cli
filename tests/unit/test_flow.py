"""Tests for flow service — stock flow via longport."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

from stk.services.flow import get_stock_flow


@patch("stk.services.flow.get_longport_ctx")
def test_get_stock_flow(mock_get_longport_ctx):
    """Test individual stock flow via longport capital_distribution."""
    cap_in = MagicMock()
    cap_in.large = Decimal(100)
    cap_in.medium = Decimal(60)
    cap_in.small = Decimal(30)

    cap_out = MagicMock()
    cap_out.large = Decimal(50)
    cap_out.medium = Decimal(40)
    cap_out.small = Decimal(20)

    dist = MagicMock()
    dist.capital_in = cap_in
    dist.capital_out = cap_out
    mock_get_longport_ctx.return_value.capital_distribution.return_value = dist
    mock_get_longport_ctx.return_value.capital_flow.return_value = []

    result = get_stock_flow("600519")
    assert result.symbol == "600519.SH"
    assert result.large_in == Decimal(100)
    assert result.large_out == Decimal(50)
    assert result.medium_in == Decimal(60)
    assert result.small_out == Decimal(20)
