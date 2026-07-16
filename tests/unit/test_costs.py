from __future__ import annotations

import pytest

from atrading.backtest import CostModel


def test_cost_fraction_scales_with_turnover() -> None:
    model = CostModel(commission_bps=1.0, slippage_bps=4.0)
    assert model.cost_fraction(0.0) == 0.0
    assert model.cost_fraction(1.0) == pytest.approx(5e-4)
    assert model.cost_fraction(2.0) == pytest.approx(1e-3)


def test_cost_rejects_negative_bps() -> None:
    with pytest.raises(ValueError, match="greater than or equal"):
        CostModel(commission_bps=-1.0)
