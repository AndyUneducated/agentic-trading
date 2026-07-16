from __future__ import annotations

from datetime import UTC, datetime

from atrading.config.settings import Settings
from atrading.core.types import Order, PortfolioState
from atrading.risk import PreTradeRiskGate, RiskLimits


def _limits(**overrides: float | int) -> RiskLimits:
    base: dict[str, float | int] = {
        "max_position_per_name": 60_000.0,
        "max_gross_exposure": 100_000.0,
        "max_notional_per_order": 50_000.0,
        "max_orders_per_interval": 5,
        "daily_loss_limit": 0.05,
    }
    base.update(overrides)
    return RiskLimits(**base)  # type: ignore[arg-type]


def _order(symbol: str, side: str, qty: float, oid: str) -> Order:
    return Order(symbol=symbol, side=side, qty=qty, client_order_id=oid)  # type: ignore[arg-type]


def _portfolio(equity: float, positions: dict[str, float]) -> PortfolioState:
    return PortfolioState(
        ts=datetime(2026, 1, 1, tzinfo=UTC), cash=equity, positions=positions, equity=equity
    )


def test_happy_path_approves() -> None:
    prices = {"AAA": 100.0}
    gate = PreTradeRiskGate(_limits(), Settings(), prices)
    decision = gate.check([_order("AAA", "buy", 100.0, "o1")], _portfolio(100_000.0, {}))
    assert len(decision.approved) == 1
    assert decision.denied == []


def test_kill_switch_denies_all() -> None:
    prices = {"AAA": 100.0}
    gate = PreTradeRiskGate(_limits(), Settings(kill_switch=True), prices)
    decision = gate.check([_order("AAA", "buy", 1.0, "o1")], _portfolio(100_000.0, {}))
    assert decision.approved == []
    assert "kill_switch" in decision.denied[0][1]


def test_over_notional_denied() -> None:
    prices = {"AAA": 100.0}
    gate = PreTradeRiskGate(_limits(), Settings(), prices)
    decision = gate.check([_order("AAA", "buy", 600.0, "o1")], _portfolio(100_000.0, {}))
    assert decision.approved == []
    assert "单笔名义" in decision.denied[0][1]


def test_position_limit_denied() -> None:
    prices = {"AAA": 100.0}
    limits = _limits(max_notional_per_order=100_000.0, max_position_per_name=40_000.0)
    gate = PreTradeRiskGate(limits, Settings(), prices)
    decision = gate.check([_order("AAA", "buy", 500.0, "o1")], _portfolio(100_000.0, {}))
    assert decision.approved == []
    assert "单标的名义" in decision.denied[0][1]


def test_gross_exposure_denied() -> None:
    prices = {"AAA": 100.0}
    gate = PreTradeRiskGate(
        _limits(max_gross_exposure=30_000.0, max_position_per_name=100_000.0), Settings(), prices
    )
    decision = gate.check([_order("AAA", "buy", 500.0, "o1")], _portfolio(100_000.0, {}))
    assert decision.approved == []
    assert "总敞口" in decision.denied[0][1]


def test_order_rate_limit() -> None:
    prices = {"AAA": 100.0, "BBB": 100.0}
    gate = PreTradeRiskGate(_limits(max_orders_per_interval=1), Settings(), prices)
    decision = gate.check(
        [_order("AAA", "buy", 10.0, "o1"), _order("BBB", "buy", 10.0, "o2")],
        _portfolio(100_000.0, {}),
    )
    assert len(decision.approved) == 1
    assert "频率" in decision.denied[0][1]


def test_daily_loss_circuit_breaker() -> None:
    prices = {"AAA": 100.0}
    gate = PreTradeRiskGate(_limits(daily_loss_limit=0.05), Settings(), prices)
    gate.set_day_start_equity(100_000.0)
    decision = gate.check([_order("AAA", "buy", 1.0, "o1")], _portfolio(90_000.0, {}))
    assert decision.approved == []
    assert "熔断" in decision.denied[0][1]
