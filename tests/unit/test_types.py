from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from atrading.core.types import Bar, Order, PortfolioState, Signal, TargetWeights


def _aware() -> datetime:
    return datetime(2026, 1, 1, tzinfo=UTC)


def test_bar_rejects_naive_datetime() -> None:
    with pytest.raises(ValidationError):
        Bar(
            symbol="AAPL",
            ts=datetime(2026, 1, 1),  # 故意的 naive datetime，用于验证被拒
            open=1,
            high=1,
            low=1,
            close=1,
            volume=1,
        )


def test_bar_accepts_aware_datetime() -> None:
    bar = Bar(symbol="AAPL", ts=_aware(), open=1, high=2, low=0.5, close=1.5, volume=100)
    assert bar.symbol == "AAPL"
    assert bar.ts.tzinfo is not None


def test_signal_confidence_bounds() -> None:
    with pytest.raises(ValidationError):
        Signal(symbol="AAPL", as_of=_aware(), name="sentiment", value=0.1, confidence=1.5)


def test_order_qty_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        Order(symbol="AAPL", side="buy", qty=0, client_order_id="x")


def test_order_defaults_market() -> None:
    order = Order(symbol="AAPL", side="buy", qty=10, client_order_id="abc")
    assert order.order_type == "market"


def test_target_weights_and_portfolio_defaults() -> None:
    tw = TargetWeights(as_of=_aware())
    assert tw.weights == {}
    ps = PortfolioState(ts=_aware(), cash=1000.0, equity=1000.0)
    assert ps.positions == {}
