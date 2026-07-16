"""目标权重 → 订单（差额下单，幂等）。

每单生成**确定性** client_order_id = hash(as_of, symbol, side, qty)，使重启/重放同一决策
不会重复下单（配合 broker/state 去重）。跳过低于 min_notional 的碎单。
"""

from __future__ import annotations

import hashlib

from atrading.core.types import Order, PortfolioState, TargetWeights


def _client_order_id(as_of_iso: str, symbol: str, side: str, qty: float) -> str:
    payload = f"{as_of_iso}|{symbol}|{side}|{qty:.6f}"
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def weights_to_orders(
    target: TargetWeights,
    portfolio: PortfolioState,
    prices: dict[str, float],
    *,
    min_notional: float = 1.0,
) -> list[Order]:
    equity = portfolio.equity
    as_of_iso = target.as_of.isoformat()
    orders: list[Order] = []

    symbols = set(target.weights) | set(portfolio.positions)
    for symbol in sorted(symbols):
        price = prices.get(symbol)
        if price is None or price <= 0:
            continue
        target_weight = target.weights.get(symbol, 0.0)
        desired_shares = target_weight * equity / price
        current_shares = portfolio.positions.get(symbol, 0.0)
        delta = desired_shares - current_shares
        notional = abs(delta) * price
        if notional < min_notional:
            continue
        side = "buy" if delta > 0 else "sell"
        qty = abs(delta)
        orders.append(
            Order(
                symbol=symbol,
                side=side,
                qty=qty,
                order_type="market",
                client_order_id=_client_order_id(as_of_iso, symbol, side, qty),
            )
        )
    return orders
