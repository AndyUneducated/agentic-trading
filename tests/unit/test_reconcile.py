from __future__ import annotations

from datetime import UTC, datetime

from atrading.core.types import Fill, Order
from atrading.execution import EngineState, Reconciler, SimulatedBroker


def _order(oid: str, qty: float = 10.0) -> Order:
    return Order(symbol="AAA", side="buy", qty=qty, client_order_id=oid)  # type: ignore[arg-type]


def test_clean_reconcile_ok() -> None:
    prices = {"AAA": 100.0}
    broker = SimulatedBroker(prices, starting_cash=100_000.0)
    broker.submit(_order("o1", qty=10.0))
    state = EngineState(positions={"AAA": 10.0}, cash=99_000.0, submitted_order_ids=["o1"])
    report = Reconciler().reconcile(broker, state)
    assert report.ok


def test_detects_unexpected_fill_and_position_drift() -> None:
    prices = {"AAA": 100.0}
    broker = SimulatedBroker(prices, starting_cash=100_000.0)
    # 券商侧"凭空多出"一笔我们从未提交的成交。
    broker.inject_fill(
        Fill(
            client_order_id="ghost",
            symbol="AAA",
            qty=7.0,
            price=100.0,
            ts=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    state = EngineState(positions={"AAA": 0.0}, cash=100_000.0, submitted_order_ids=[])
    report = Reconciler().reconcile(broker, state)
    assert not report.ok
    assert "ghost" in report.unexpected_fills
    assert "AAA" in report.position_mismatches
