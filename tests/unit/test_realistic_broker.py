from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atrading.core.types import Order
from atrading.execution.costs import CommissionModel, SlippageModel
from atrading.execution.realistic_broker import RealisticBroker

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _order(symbol: str, side: str, qty: float, oid: str = "o1") -> Order:
    return Order(symbol=symbol, side=side, qty=qty, order_type="market", client_order_id=oid)


def test_immediate_full_fill_frictionless() -> None:
    broker = RealisticBroker({"AAA": 100.0})
    broker.submit(_order("AAA", "buy", 10))
    fills = broker.advance(now=_NOW)
    assert len(fills) == 1
    assert fills[0].qty == pytest.approx(10)
    state = broker.get_positions()
    assert state.positions["AAA"] == pytest.approx(10)
    assert state.cash == pytest.approx(99_000.0)


def test_partial_fill_by_volume_cap() -> None:
    broker = RealisticBroker({"AAA": 100.0}, participation_rate=0.1)
    broker.submit(_order("AAA", "buy", 10))
    first = broker.advance(now=_NOW, volumes={"AAA": 50.0})  # cap = 0.1*50 = 5
    assert first[0].qty == pytest.approx(5)
    assert broker.get_open_orders()[0].qty == pytest.approx(5)
    second = broker.advance(now=_NOW, volumes={"AAA": 50.0})
    assert second[0].qty == pytest.approx(5)
    assert broker.get_open_orders() == []


def test_latency_gates_fill() -> None:
    broker = RealisticBroker({"AAA": 100.0}, latency_steps=1)
    broker.submit(_order("AAA", "buy", 5))
    assert broker.advance(now=_NOW) == []  # 延迟未到
    fills = broker.advance(now=_NOW)
    assert len(fills) == 1


def test_commission_reduces_cash() -> None:
    broker = RealisticBroker({"AAA": 100.0}, commission=CommissionModel(bps=10.0))
    broker.submit(_order("AAA", "buy", 10))
    fills = broker.advance(now=_NOW)
    assert fills[0].fee == pytest.approx(1.0)  # 10bp of 1000
    assert broker.get_positions().cash == pytest.approx(100_000 - 1000 - 1.0)


def test_slippage_moves_fill_price() -> None:
    broker = RealisticBroker({"AAA": 100.0}, slippage=SlippageModel(bps=50.0))
    broker.submit(_order("AAA", "buy", 10))
    fills = broker.advance(now=_NOW)
    assert fills[0].price == pytest.approx(100.5)


def test_idempotent_submit() -> None:
    broker = RealisticBroker({"AAA": 100.0})
    broker.submit(_order("AAA", "buy", 10, oid="dup"))
    broker.submit(_order("AAA", "buy", 10, oid="dup"))  # 重复 id 忽略
    fills = broker.advance(now=_NOW)
    assert len(fills) == 1
    assert broker.get_positions().positions["AAA"] == pytest.approx(10)


def test_sell_increases_cash() -> None:
    broker = RealisticBroker({"AAA": 100.0}, starting_cash=0.0)
    broker.submit(_order("AAA", "sell", 5))
    broker.advance(now=_NOW)
    state = broker.get_positions()
    assert state.positions["AAA"] == pytest.approx(-5)
    assert state.cash == pytest.approx(500.0)
