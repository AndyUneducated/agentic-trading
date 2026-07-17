"""回测-实盘同源 parity（M8/ADR-0003）：无摩擦下高保真 broker == 即时模拟 broker。

同一订单流分别过 SimulatedBroker 与 RealisticBroker（零费/零滑点/零延迟/满参与），持仓与
现金必须一致——证明两者行为同源，drift 只会来自显式配置的真实摩擦（费用/滑点/延迟）。
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atrading.core.types import Order
from atrading.execution.costs import CommissionModel, SlippageModel
from atrading.execution.paper_broker import SimulatedBroker
from atrading.execution.realistic_broker import RealisticBroker

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _order(symbol: str, side: str, qty: float, oid: str) -> Order:
    return Order(symbol=symbol, side=side, qty=qty, order_type="market", client_order_id=oid)


def test_frictionless_realistic_matches_simulated() -> None:
    prices = {"AAA": 100.0, "BBB": 50.0}
    orders = [
        _order("AAA", "buy", 10, "o1"),
        _order("BBB", "buy", 20, "o2"),
        _order("AAA", "sell", 4, "o3"),
    ]

    sim = SimulatedBroker(dict(prices))
    realistic = RealisticBroker(dict(prices))  # 默认零摩擦、满参与、零延迟

    for order in orders:
        sim.submit(order)
        realistic.submit(order)
    realistic.advance(now=_NOW)

    sim_state = sim.get_positions()
    real_state = realistic.get_positions()
    assert real_state.cash == pytest.approx(sim_state.cash)
    assert real_state.positions == pytest.approx(sim_state.positions)
    assert real_state.equity == pytest.approx(sim_state.equity)


def test_friction_creates_bounded_drift() -> None:
    prices = {"AAA": 100.0}
    sim = SimulatedBroker(dict(prices))
    realistic = RealisticBroker(
        dict(prices),
        commission=CommissionModel(bps=10.0),
        slippage=SlippageModel(bps=50.0),
    )
    order = _order("AAA", "buy", 10, "o1")
    sim.submit(order)
    realistic.submit(order)
    realistic.advance(now=_NOW)

    # 摩擦让高保真 broker 现金更少（滑点抬价 + 手续费）——drift 完全来自显式成本。
    assert realistic.get_positions().cash < sim.get_positions().cash
