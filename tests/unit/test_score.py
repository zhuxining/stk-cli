"""Tests for multi-indicator resonance scoring service."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from stk.errors import IndicatorError
from stk.services.score import calc_score


@patch("stk.services.flow.get_stock_flow")
@patch("stk.services.score.get_history")
def test_calc_score_basic(mock_history, mock_flow, make_candles):
    """Test basic scoring returns valid structure."""
    mock_history.return_value = make_candles(60)
    mock_flow.side_effect = Exception("no flow data")

    result = calc_score("600519")

    assert result.symbol == "600519"
    assert 0 <= result.total_score <= 100
    assert result.rating in ("A+", "A", "B+", "B", "C")
    assert len(result.dimensions) == 6
    assert isinstance(result.buy_signals, list)
    assert isinstance(result.sell_signals, list)


@patch("stk.services.flow.get_stock_flow")
@patch("stk.services.score.get_history")
def test_score_dimensions_complete(mock_history, mock_flow, make_candles):
    """Test all 6 dimensions are present with correct max scores."""
    mock_history.return_value = make_candles(60)
    mock_flow.side_effect = Exception("no flow data")

    result = calc_score("600519")

    dim_names = {d.name for d in result.dimensions}
    assert dim_names == {"RSI", "KDJ", "MACD", "BOLL", "量价", "资金"}

    max_scores = {d.name: d.max_score for d in result.dimensions}
    assert max_scores["RSI"] == 20
    assert max_scores["KDJ"] == 20
    assert max_scores["MACD"] == 15
    assert max_scores["BOLL"] == 15
    assert max_scores["量价"] == 15
    assert max_scores["资金"] == 15


@patch("stk.services.flow.get_stock_flow")
@patch("stk.services.score.get_history")
def test_score_dimension_scores_not_exceed_max(mock_history, mock_flow, make_candles):
    """Test no dimension exceeds its max score."""
    mock_history.return_value = make_candles(60)
    mock_flow.side_effect = Exception("no flow data")

    result = calc_score("600519")

    for dim in result.dimensions:
        assert dim.score <= dim.max_score, f"{dim.name} score {dim.score} > max {dim.max_score}"
        assert dim.score >= 0, f"{dim.name} score {dim.score} < 0"


@patch("stk.services.flow.get_stock_flow")
@patch("stk.services.score.get_history")
def test_score_atr_fields(mock_history, mock_flow, make_candles):
    """Test ATR-based trade points are calculated."""
    mock_history.return_value = make_candles(60)
    mock_flow.side_effect = Exception("no flow data")

    result = calc_score("600519")

    assert result.atr is not None
    assert result.atr > 0
    assert result.stop_loss is not None
    assert result.take_profit is not None
    assert result.stop_loss < result.take_profit
    assert result.risk_reward_ratio is not None
    assert result.risk_reward_ratio > 0


@patch("stk.services.score.get_history")
def test_score_insufficient_data(mock_history, make_candles):
    """Test error when insufficient history data."""
    mock_history.return_value = make_candles(10)

    with pytest.raises(IndicatorError, match="Insufficient"):
        calc_score("600519")


@patch("stk.services.score.get_history")
def test_score_no_data(mock_history):
    """Test error when no history data."""
    mock_history.return_value = []

    with pytest.raises(IndicatorError, match="Insufficient"):
        calc_score("600519")


@patch("stk.services.flow.get_stock_flow")
@patch("stk.services.score.get_history")
def test_score_with_flow_data(mock_history, mock_flow, make_candles):
    """Test scoring with flow data available."""
    mock_history.return_value = make_candles(60)

    flow = MagicMock()
    flow.large_in = Decimal(10000000)
    flow.large_out = Decimal(3000000)
    flow.medium_in = Decimal(5000000)
    flow.medium_out = Decimal(2000000)
    mock_flow.return_value = flow

    result = calc_score("600519")

    flow_dim = next(d for d in result.dimensions if d.name == "资金")
    assert flow_dim.score > 0
    assert flow_dim.signal is not None
    assert "流入" in flow_dim.signal


@patch("stk.services.flow.get_stock_flow")
@patch("stk.services.score.get_history")
def test_rating_mapping(mock_history, mock_flow, make_candles):
    """Test rating is derived from total score."""
    mock_history.return_value = make_candles(60)
    mock_flow.side_effect = Exception("no flow data")

    result = calc_score("600519")

    if result.total_score >= 85:
        assert result.rating == "A+"
    elif result.total_score >= 70:
        assert result.rating == "A"
    elif result.total_score >= 60:
        assert result.rating == "B+"
    elif result.total_score >= 50:
        assert result.rating == "B"
    else:
        assert result.rating == "C"
