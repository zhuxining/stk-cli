"""Tests for board quote in get_quote service."""

from decimal import Decimal
from unittest.mock import patch

import pandas as pd
import pytest

from stk.errors import SourceError
from stk.models.common import TargetType
from stk.services.quote import get_quote


@patch("stk.services.quote._get_board_quote")
def test_get_sector_quote(mock_get_board_quote):
    """Test sector board quote."""
    from stk.models.quote import Quote

    mock_get_board_quote.return_value = Quote(
        symbol="BK0001",
        name="半导体",
        last=Decimal("1200.5"),
        change=Decimal("15.3"),
        change_pct=Decimal("1.29"),
        turnover=Decimal("5e12"),
    )

    result = get_quote("半导体", target_type=TargetType.SECTOR)
    assert result.name == "半导体"
    assert result.last == Decimal("1200.5")
    assert result.change_pct == Decimal("1.29")
    mock_get_board_quote.assert_called_once_with("半导体", board_type="sector")


@patch("stk.services.quote._get_board_quote")
def test_get_concept_quote(mock_get_board_quote):
    """Test concept board quote."""
    from stk.models.quote import Quote

    mock_get_board_quote.return_value = Quote(
        symbol="BK0100",
        name="ChatGPT 概念",
        last=Decimal("500.0"),
        change=None,
        change_pct=Decimal("2.5"),
        turnover=Decimal("1e12"),
    )

    result = get_quote("ChatGPT", target_type=TargetType.CONCEPT)
    assert result.name == "ChatGPT 概念"
    assert result.last == Decimal("500.0")
    mock_get_board_quote.assert_called_once_with("ChatGPT", board_type="concept")


@patch("stk.services.quote._get_board_quote")
def test_get_sector_quote_not_found(mock_get_board_quote):
    """Test sector not found raises SourceError."""
    mock_get_board_quote.side_effect = SourceError("Sector '不存在的板块' not found")

    with pytest.raises(SourceError, match="not found"):
        get_quote("不存在的板块", target_type=TargetType.SECTOR)
