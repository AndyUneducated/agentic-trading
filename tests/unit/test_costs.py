from __future__ import annotations

import pytest

from atrading.execution.costs import CommissionModel, SlippageModel


def test_commission_per_share_and_bps() -> None:
    model = CommissionModel(per_share=0.005, bps=1.0)  # 0.005/股 + 1bp 名义
    # 100 股 @ $100：0.5（每股）+ 1.0（名义 1bp of 10000）= 1.5
    assert model.commission(100, 100.0) == pytest.approx(1.5)


def test_commission_min_per_order() -> None:
    model = CommissionModel(bps=1.0, min_per_order=1.0)
    assert model.commission(1, 100.0) == pytest.approx(1.0)  # 名义费 0.01 < 下限 → 取下限


def test_commission_zero_for_no_qty() -> None:
    assert CommissionModel(min_per_order=5.0).commission(0, 100.0) == 0.0


def test_slippage_direction() -> None:
    model = SlippageModel(bps=50.0)  # 50bp 固定
    assert model.fill_price("buy", 100.0) == pytest.approx(100.5)  # 买向上滑
    assert model.fill_price("sell", 100.0) == pytest.approx(99.5)  # 卖向下滑


def test_slippage_market_impact_scales_with_participation() -> None:
    model = SlippageModel(bps=0.0, impact_bps_per_participation=100.0)
    # 参与率 0.5 → 50bp 冲击 → 买价 100*(1+0.005)=100.5
    assert model.fill_price("buy", 100.0, participation=0.5) == pytest.approx(100.5)
