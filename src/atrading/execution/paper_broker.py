"""离线模拟 broker（实现 core.Broker）。

**不接真实资金、不联网**：在进程内按当前价格即时成交，用于跑通闭环与测试。真实
Alpaca paper / CCXT testnet 适配按同一 core.Broker 协议后续替换（ADR-0006）。

幂等：按 client_order_id 去重——重复提交同一 id 不二次成交（支撑崩溃恢复/重放）。
"""

from __future__ import annotations

from datetime import UTC, datetime

from atrading.core.types import Fill, Order, PortfolioState


class SimulatedBroker:
    def __init__(self, prices: dict[str, float], *, starting_cash: float = 100_000.0) -> None:
        self._prices = prices  # 由调用方(loop)持续更新的实时价引用
        self._cash = starting_cash
        self._positions: dict[str, float] = {}
        self._fills: list[Fill] = []
        self._seen_order_ids: set[str] = set()

    def submit(self, order: Order) -> None:
        if order.client_order_id in self._seen_order_ids:
            return  # 幂等去重
        price = self._prices.get(order.symbol)
        if price is None or price <= 0:
            return  # 无价 → 安全不成交
        self._seen_order_ids.add(order.client_order_id)
        signed_qty = order.qty if order.side == "buy" else -order.qty
        self._positions[order.symbol] = self._positions.get(order.symbol, 0.0) + signed_qty
        self._cash -= signed_qty * price
        self._fills.append(
            Fill(
                client_order_id=order.client_order_id,
                symbol=order.symbol,
                qty=order.qty,
                price=price,
                ts=datetime.now(tz=UTC),
            )
        )

    def advance(self, now: datetime) -> list[Fill]:
        return []  # 即时成交模型：submit 时已成交，无需推进撮合

    def get_positions(self) -> PortfolioState:
        invested = sum(
            shares * self._prices.get(symbol, 0.0) for symbol, shares in self._positions.items()
        )
        return PortfolioState(
            ts=datetime.now(tz=UTC),
            cash=self._cash,
            positions=dict(self._positions),
            equity=self._cash + invested,
        )

    def get_open_orders(self) -> list[Order]:
        return []  # 即时成交模型：无挂单

    def get_fills(self, since: datetime) -> list[Fill]:
        return [fill for fill in self._fills if fill.ts >= since]

    # --- 测试/对账辅助（非 core.Broker 协议的一部分） ---
    def inject_fill(self, fill: Fill) -> None:
        """注入一笔"券商侧发生但我们未记录"的成交，用于对账测试。"""
        self._fills.append(fill)
        signed = fill.qty  # 视为买入方向的外部成交
        self._positions[fill.symbol] = self._positions.get(fill.symbol, 0.0) + signed
