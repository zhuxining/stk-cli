"""Tests for multi-indicator resonance scoring service."""

from unittest.mock import patch

import pytest

from stk.errors import IndicatorError
from stk.services.score import calc_score


@patch("stk.services.score.get_history")
def test_calc_score_basic(mock_history, make_candles):
    """Test basic scoring returns valid structure."""
    mock_history.return_value = make_candles(60)

    result = calc_score("600519")

    assert result.symbol == "600519"
    assert 0 <= result.total_score <= 100
    # 7 dims: 动量, MACD, BOLL, 量价, 趋势, 资金流, 背离
    assert len(result.dimensions) == 7
    assert isinstance(result.signals, list)


@patch("stk.services.score.get_history")
def test_score_dimensions_complete(mock_history, make_candles):
    """Test all 7 dimensions are present with correct max scores."""
    mock_history.return_value = make_candles(60)

    result = calc_score("600519")

    dim_names = {d.name for d in result.dimensions}
    assert dim_names == {"动量", "MACD", "BOLL", "量价", "趋势", "资金流", "背离"}

    max_scores = {d.name: d.max_score for d in result.dimensions}
    assert max_scores["动量"] == 15
    assert max_scores["MACD"] == 15
    assert max_scores["BOLL"] == 15
    assert max_scores["量价"] == 10
    assert max_scores["趋势"] == 20
    assert max_scores["资金流"] == 15
    assert max_scores["背离"] == 10


@patch("stk.services.score.get_history")
def test_score_dimension_scores_not_exceed_max(mock_history, make_candles):
    """Test no dimension exceeds its max score."""
    mock_history.return_value = make_candles(60)

    result = calc_score("600519")

    for dim in result.dimensions:
        assert dim.score <= dim.max_score, f"{dim.name} score {dim.score} > max {dim.max_score}"
        assert dim.score >= 0, f"{dim.name} score {dim.score} < 0"


@patch("stk.services.score.get_history")
def test_score_atr_fields(mock_history, make_candles):
    """Test ATR-based trade points are calculated."""
    mock_history.return_value = make_candles(60)

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


@patch("stk.services.score.get_history")
def test_score_mfi_dimension(mock_history, make_candles):
    """Test MFI (Money Flow Index) dimension is calculated."""
    mock_history.return_value = make_candles(60)

    result = calc_score("600519")

    mfi_dim = next(d for d in result.dimensions if d.name == "资金流")
    assert mfi_dim.score >= 0
    assert mfi_dim.max_score == 15
    assert mfi_dim.signal is not None
    assert "MFI=" in mfi_dim.signal


@patch("stk.services.score.get_history")
def test_score_signals_have_prefix(mock_history, make_candles):
    """Test signals have direction prefix [买]/[卖]."""
    mock_history.return_value = make_candles(60)

    result = calc_score("600519")

    for sig in result.signals:
        assert sig.startswith("[买] ") or sig.startswith("[卖] "), f"Signal missing prefix: {sig}"


@patch("stk.services.score.get_history")
def test_score_adx(mock_history, make_candles):
    """Test ADX field is populated."""
    mock_history.return_value = make_candles(60)

    result = calc_score("600519")

    assert result.adx is not None
