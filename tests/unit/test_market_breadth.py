"""Tests for market breadth service."""

from unittest.mock import patch

import pandas as pd

from stk.services.market import get_breadth


@patch("stk.services.market.ak")
def test_get_breadth(mock_ak):
    """Test market breadth aggregation."""
    spot_df = pd.DataFrame({"涨跌幅": [1.5, -2.0, 0.0, 3.0, -1.0, 0.0, 5.0]})
    mock_ak.stock_zh_a_spot_em.return_value = spot_df

    zt_df = pd.DataFrame({"代码": ["000001", "000002", "000003"]})
    mock_ak.stock_zt_pool_em.return_value = zt_df

    dt_df = pd.DataFrame({"代码": ["600001"]})
    mock_ak.stock_zt_pool_dtgc_em.return_value = dt_df

    result = get_breadth()
    assert result.up_count == 3
    assert result.down_count == 2
    assert result.flat_count == 2
    assert result.limit_up == 3
    assert result.limit_down == 1


@patch("stk.services.market.ak")
def test_get_breadth_zt_fails_gracefully(mock_ak):
    """Test breadth still works if limit-up/down APIs fail."""
    spot_df = pd.DataFrame({"涨跌幅": [1.0, -1.0]})
    mock_ak.stock_zh_a_spot_em.return_value = spot_df
    mock_ak.stock_zt_pool_em.side_effect = RuntimeError("api error")
    mock_ak.stock_zt_pool_dtgc_em.side_effect = RuntimeError("api error")

    result = get_breadth()
    assert result.up_count == 1
    assert result.down_count == 1
    assert result.limit_up == 0
    assert result.limit_down == 0
