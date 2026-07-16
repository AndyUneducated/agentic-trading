"""预交易风控门（硬护栏）。

所有订单**必过**，不通过即 denied(附原因)。风控前置于执行：execution 只接受
RiskGate.approved 的订单，无旁路（有测试覆盖）。借鉴 Nautilus RiskEngine：
kill switch / 交易模式 / 日亏熔断为全局闸门；名义/仓位/敞口/频率为逐单闸门。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from atrading.config.settings import Settings
from atrading.core.interfaces import RiskDecision
from atrading.core.types import Order, PortfolioState


class RiskLimits(BaseModel):
    max_position_per_name: float = Field(gt=0)  # 单标的名义上限（金额）
    max_gross_exposure: float = Field(gt=0)  # 总名义敞口上限（金额）
    max_notional_per_order: float = Field(gt=0)  # 单笔名义上限（金额）
    max_orders_per_interval: int = Field(gt=0)  # 单个决策周期最多下单数
    daily_loss_limit: float = Field(gt=0, le=1)  # 日内亏损熔断（占日初权益比例）


class PreTradeRiskGate:
    """实现 core.RiskGate。价格由外部(loop)持续更新的 `prices` 引用提供。"""

    def __init__(
        self,
        limits: RiskLimits,
        settings: Settings,
        prices: dict[str, float],
    ) -> None:
        self._limits = limits
        self._settings = settings
        self._prices = prices
        self._day_start_equity: float | None = None

    def set_day_start_equity(self, equity: float) -> None:
        self._day_start_equity = equity

    def _deny_all(self, orders: list[Order], reason: str) -> RiskDecision:
        return RiskDecision(approved=[], denied=[(order, reason) for order in orders])

    def check(self, orders: list[Order], portfolio: PortfolioState) -> RiskDecision:
        # --- 全局闸门：任一触发则全拒 ---
        if self._settings.kill_switch:
            return self._deny_all(orders, "kill_switch 已激活")
        if not self._settings.can_trade:
            return self._deny_all(orders, f"trading_mode={self._settings.trading_mode} 未获准交易")
        if self._day_start_equity is not None:
            floor = self._day_start_equity * (1.0 - self._limits.daily_loss_limit)
            if portfolio.equity <= floor:
                return self._deny_all(orders, "触发日内亏损熔断")

        # --- 逐单闸门 ---
        approved: list[Order] = []
        denied: list[tuple[Order, str]] = []
        # 以当前持仓名义为基线，累加已放行订单对敞口的影响。
        position_notional: dict[str, float] = {
            symbol: abs(shares) * self._prices.get(symbol, 0.0)
            for symbol, shares in portfolio.positions.items()
        }
        gross_notional = sum(position_notional.values())
        orders_count = 0

        for order in orders:
            price = self._prices.get(order.symbol)
            if price is None or price <= 0:
                denied.append((order, "无有效价格"))
                continue
            order_notional = order.qty * price

            if orders_count >= self._limits.max_orders_per_interval:
                denied.append((order, "超过单周期下单频率上限"))
                continue
            if order_notional > self._limits.max_notional_per_order:
                denied.append((order, "超过单笔名义上限"))
                continue

            signed = order_notional if order.side == "buy" else -order_notional
            projected_position = abs(position_notional.get(order.symbol, 0.0) + signed)
            if projected_position > self._limits.max_position_per_name:
                denied.append((order, "超过单标的名义上限"))
                continue
            projected_gross = gross_notional + order_notional
            if projected_gross > self._limits.max_gross_exposure:
                denied.append((order, "超过总敞口上限"))
                continue

            approved.append(order)
            orders_count += 1
            position_notional[order.symbol] = position_notional.get(order.symbol, 0.0) + signed
            gross_notional = projected_gross

        return RiskDecision(approved=approved, denied=denied)
