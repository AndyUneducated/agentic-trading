"""高保真执行模拟 broker（M8）：延迟 + 部分成交 + 手续费 + 滑点。

实现同一个 `core.Broker` 协议（与 SimulatedBroker 可互换），把执行从"即时全额成交"
升级为更接近真实券商/撮合的机制：
- 延迟：订单需经过 `latency_steps` 次 `advance` 才开始成交。
- 部分成交：每次 `advance` 至多成交 `participation_rate × 当期成交量`，剩余留作挂单。
- 成本：CommissionModel + SlippageModel（与回测共用 → 回测-实盘同源，ADR-0003）。

真实撮合/订单簿保真（Nautilus）为后续真实基建；本类提供离线可测的执行真实性。
幂等：按 client_order_id 去重。
"""

from __future__ import annotations

from datetime import UTC, datetime

from atrading.core.types import Fill, Order, PortfolioState
from atrading.execution.costs import CommissionModel, SlippageModel


class _Pending:
    __slots__ = ("order", "remaining", "submit_step")

    def __init__(self, order: Order, submit_step: int) -> None:
        self.order = order
        self.remaining = order.qty
        self.submit_step = submit_step


class RealisticBroker:
    def __init__(
        self,
        prices: dict[str, float],
        *,
        starting_cash: float = 100_000.0,
        commission: CommissionModel | None = None,
        slippage: SlippageModel | None = None,
        latency_steps: int = 0,
        participation_rate: float = 1.0,
    ) -> None:
        if participation_rate <= 0:
            msg = "participation_rate 必须为正"
            raise ValueError(msg)
        self._prices = prices  # 由调用方持续更新的实时价引用
        self._cash = starting_cash
        self._positions: dict[str, float] = {}
        self._fills: list[Fill] = []
        self._pending: list[_Pending] = []
        self._seen_order_ids: set[str] = set()
        self._commission = commission or CommissionModel()
        self._slippage = slippage or SlippageModel()
        self._latency_steps = latency_steps
        self._participation_rate = participation_rate
        self._step = 0

    def submit(self, order: Order) -> None:
        if order.client_order_id in self._seen_order_ids:
            return  # 幂等去重
        self._seen_order_ids.add(order.client_order_id)
        self._pending.append(_Pending(order, self._step))

    def advance(
        self, now: datetime | None = None, volumes: dict[str, float] | None = None
    ) -> list[Fill]:
        """推进一个撮合步：按延迟门控 + 参与率上限对挂单做（部分）成交。返回本步新成交。

        `now` 位置或关键字均可（与 core.Broker 协议 `advance(now)` 兼容）；`volumes`
        为可选的当期成交量（用于参与率上限），主循环未提供时退化为无量约束。
        """
        now = now or datetime.now(tz=UTC)
        self._step += 1
        new_fills: list[Fill] = []
        still_pending: list[_Pending] = []
        for pending in self._pending:
            filled = self._try_fill(pending, now=now, volumes=volumes)
            if filled is not None:
                new_fills.append(filled)
            if pending.remaining > 1e-9:
                still_pending.append(pending)
        self._pending = still_pending
        return new_fills

    def _try_fill(
        self, pending: _Pending, *, now: datetime, volumes: dict[str, float] | None
    ) -> Fill | None:
        order = pending.order
        if self._step - pending.submit_step <= self._latency_steps:
            return None  # 延迟未到
        price = self._prices.get(order.symbol)
        if price is None or price <= 0:
            return None  # 无价 → 安全不成交

        cap = pending.remaining
        volume = None if volumes is None else volumes.get(order.symbol)
        if volume is not None:
            cap = min(cap, self._participation_rate * volume)
        fill_qty = min(pending.remaining, cap)
        if fill_qty <= 0:
            return None

        participation = fill_qty / volume if volume else 0.0
        fill_price = self._slippage.fill_price(order.side, price, participation=participation)
        fee = self._commission.commission(fill_qty, fill_price)
        signed = fill_qty if order.side == "buy" else -fill_qty
        self._positions[order.symbol] = self._positions.get(order.symbol, 0.0) + signed
        self._cash -= signed * fill_price + fee
        pending.remaining -= fill_qty
        fill = Fill(
            client_order_id=order.client_order_id,
            symbol=order.symbol,
            qty=fill_qty,
            price=fill_price,
            ts=now,
            fee=fee,
        )
        self._fills.append(fill)
        return fill

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
        return [
            p.order.model_copy(update={"qty": p.remaining})
            for p in self._pending
            if p.remaining > 1e-9
        ]

    def get_fills(self, since: datetime) -> list[Fill]:
        return [fill for fill in self._fills if fill.ts >= since]
