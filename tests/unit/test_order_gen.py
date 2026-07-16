from __future__ import annotations

from datetime import UTC, datetime

from atrading.core.types import PortfolioState, TargetWeights
from atrading.execution import weights_to_orders


def _portfolio(equity: float, positions: dict[str, float]) -> PortfolioState:
    return PortfolioState(
        ts=datetime(2026, 1, 1, tzinfo=UTC),
        cash=equity - sum(positions.values()),
        positions=positions,
        equity=equity,
    )


def test_generates_delta_order_and_deterministic_id() -> None:
    target = TargetWeights(as_of=datetime(2026, 1, 1, tzinfo=UTC), weights={"AAA": 0.5})
    portfolio = _portfolio(100_000.0, {})
    prices = {"AAA": 100.0}

    orders_a = weights_to_orders(target, portfolio, prices)
    orders_b = weights_to_orders(target, portfolio, prices)
    assert len(orders_a) == 1
    assert orders_a[0].side == "buy"
    assert orders_a[0].qty == 500.0
    assert orders_a[0].client_order_id == orders_b[0].client_order_id  # 幂等


def test_skips_tiny_and_zero_delta() -> None:
    as_of = datetime(2026, 1, 1, tzinfo=UTC)
    prices = {"AAA": 100.0}

    tiny = TargetWeights(as_of=as_of, weights={"AAA": 0.0000001})
    assert weights_to_orders(tiny, _portfolio(100_000.0, {}), prices) == []

    # 已持有目标仓位 → delta 0 → 无单
    held = TargetWeights(as_of=as_of, weights={"AAA": 0.5})
    assert weights_to_orders(held, _portfolio(100_000.0, {"AAA": 500.0}), prices) == []
