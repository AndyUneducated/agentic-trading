"""目标权重 → 订单（差额下单，幂等）。

每单生成**确定性** client_order_id = hash(as_of, symbol, side, qty)，使重启/重放同一决策
不会重复下单（配合 broker/state 去重）。跳过低于 min_notional 的碎单。

**卖单优先**：返回列表中所有 sell 排在 buy 之前。再平衡时先卖出超配标的释放现金，再买入
低配标的——否则对**校验买力的真实/模拟券商**（如 paper-trading-platform）会因买单先于卖单
成交而触发 `insufficient_buying_power` 拒单（我方宽松的 SimulatedBroker 会掩盖此问题）。
在 gross 敞口 ≤ 1 时，先卖后买保证买单资金充足（对齐回测-实盘一致，ADR-0003）。
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
    cash_buffer: float = 0.005,
) -> list[Order]:
    """把目标权重转成差额订单（卖单优先 + 买力约束）。

    `cash_buffer`：买单总额预留的现金比例（默认 0.5%），吸收成交价/量子取整漂移，避免"目标
    ~100% 满仓时最后一笔买单超出可用现金几分钱"而被真实券商拒单（buying-power reject）。
    """
    equity = portfolio.equity
    as_of_iso = target.as_of.isoformat()
    sells: list[Order] = []
    buy_specs: list[tuple[Order, float, float]] = []  # (order, notional, price)
    sell_proceeds = 0.0

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
        if delta < 0:
            qty = -delta
            sells.append(
                Order(
                    symbol=symbol,
                    side="sell",
                    qty=qty,
                    order_type="market",
                    client_order_id=_client_order_id(as_of_iso, symbol, "sell", qty),
                )
            )
            sell_proceeds += notional
        else:
            order = Order(
                symbol=symbol,
                side="buy",
                qty=delta,
                order_type="market",
                client_order_id=_client_order_id(as_of_iso, symbol, "buy", delta),
            )
            buy_specs.append((order, notional, price))

    # 买力上限：可用现金 = 当前现金 + 卖单回款（卖单先成交），再预留 cash_buffer。
    available = max(0.0, (portfolio.cash + sell_proceeds) * (1.0 - cash_buffer))
    buys: list[Order] = []
    spent = 0.0
    for order, notional, price in buy_specs:
        if spent + notional <= available:
            buys.append(order)
            spent += notional
            continue
        remaining = available - spent
        if remaining >= min_notional:  # 现金不足全额 → 缩量至剩余买力（部分再平衡）
            new_qty = remaining / price
            buys.append(
                order.model_copy(
                    update={
                        "qty": new_qty,
                        "client_order_id": _client_order_id(
                            as_of_iso, order.symbol, "buy", new_qty
                        ),
                    }
                )
            )
            spent = available
        # 否则跳过该买单（现金已耗尽）
    # 卖单优先：先释放现金，避免买单先行导致的买力不足拒单（见模块 docstring）。
    return sells + buys
