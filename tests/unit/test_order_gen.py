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


def test_sells_are_ordered_before_buys() -> None:
    # 回归：再平衡须先卖后买——即便买入标的(AAA)字母序在卖出标的(ZZZ)之前。
    as_of = datetime(2026, 1, 1, tzinfo=UTC)
    prices = {"AAA": 100.0, "ZZZ": 100.0}
    # 持有 ZZZ 1000 股(=100k)、现金 0；目标各半 → 卖 ZZZ 500、买 AAA。
    portfolio = PortfolioState(ts=as_of, cash=0.0, positions={"ZZZ": 1000.0}, equity=100_000.0)
    target = TargetWeights(as_of=as_of, weights={"AAA": 0.5, "ZZZ": 0.5})
    orders = weights_to_orders(target, portfolio, prices)
    sides = [o.side for o in orders]
    assert sides == ["sell", "buy"]  # 卖单在买单之前（防买力不足拒单）


def test_buys_capped_to_available_buying_power() -> None:
    # 回归：目标满仓(1.0)时买单总额不得超过可用买力（现金 + 卖单回款）× (1-buffer)，
    # 否则对校验买力的真实/模拟券商会触发 insufficient_buying_power 拒单。
    as_of = datetime(2026, 1, 1, tzinfo=UTC)
    prices = {"AAA": 100.0, "BBB": 100.0}
    # 持有 BBB 500(=50k) + 现金 50k；目标全仓 AAA → 卖 BBB 全部、买 AAA。
    portfolio = PortfolioState(ts=as_of, cash=50_000.0, positions={"BBB": 500.0}, equity=100_000.0)
    target = TargetWeights(as_of=as_of, weights={"AAA": 1.0})
    orders = weights_to_orders(target, portfolio, prices)

    sells = [o for o in orders if o.side == "sell"]
    buys = [o for o in orders if o.side == "buy"]
    assert sells and buys
    buy_notional = sum(o.qty * prices[o.symbol] for o in buys)
    sell_proceeds = sum(o.qty * prices[o.symbol] for o in sells)
    buying_power = portfolio.cash + sell_proceeds
    assert buy_notional <= buying_power + 1e-6  # 不超买力
    assert buy_notional < buying_power  # 预留了 cash_buffer
