from __future__ import annotations

from datetime import UTC, datetime

from atrading.core.types import Order
from atrading.execution import SimulatedBroker


def _order(oid: str, symbol: str = "AAA", side: str = "buy", qty: float = 10.0) -> Order:
    return Order(symbol=symbol, side=side, qty=qty, client_order_id=oid)  # type: ignore[arg-type]


def test_submit_fills_and_updates_positions() -> None:
    prices = {"AAA": 100.0}
    broker = SimulatedBroker(prices, starting_cash=100_000.0)
    broker.submit(_order("o1", qty=10.0))
    state = broker.get_positions()
    assert state.positions["AAA"] == 10.0
    assert state.cash == 99_000.0
    assert state.equity == 100_000.0
    assert len(broker.get_fills(datetime(1970, 1, 1, tzinfo=UTC))) == 1


def test_idempotent_dedup() -> None:
    prices = {"AAA": 100.0}
    broker = SimulatedBroker(prices, starting_cash=100_000.0)
    broker.submit(_order("dup", qty=10.0))
    broker.submit(_order("dup", qty=10.0))  # 同 id → 忽略
    assert broker.get_positions().positions["AAA"] == 10.0
    assert len(broker.get_fills(datetime(1970, 1, 1, tzinfo=UTC))) == 1
