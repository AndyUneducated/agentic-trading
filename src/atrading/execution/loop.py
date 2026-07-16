"""交易主循环：observe → 信号 → 决策 → 风控门 → 执行 → 对账 → 持久化。

复用 M3 统一 DecisionPolicy（回测-实盘一致，ADR-0003）；环境差异隔离在 DataSource/
Broker/Clock。任何一步异常 → **安全降级**（本步不交易，记录），进入下一循环。
只提交 RiskGate.approved 的订单；幂等 client_order_id 支撑崩溃恢复不重复下单。
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from atrading.core.interfaces import (
    Broker,
    DataSource,
    DecisionContext,
    DecisionPolicy,
    SignalSource,
)
from atrading.core.strategy_config import StrategyConfig
from atrading.core.types import Bar, Order
from atrading.execution.order_gen import weights_to_orders
from atrading.execution.reconcile import Reconciler
from atrading.execution.state_store import EngineState, StateStore
from atrading.risk.gate import PreTradeRiskGate

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


class StepReport(BaseModel):
    ts: datetime
    target_weights: dict[str, float] = Field(default_factory=dict)
    submitted_order_ids: list[str] = Field(default_factory=list)
    denied: list[tuple[Order, str]] = Field(default_factory=list)
    reconcile_ok: bool = True
    degraded: bool = False
    error: str | None = None


class TradingLoop:
    def __init__(
        self,
        *,
        policy: DecisionPolicy,
        data: DataSource,
        signals: SignalSource | None,
        risk_gate: PreTradeRiskGate,
        broker: Broker,
        state_store: StateStore,
        config: StrategyConfig,
        prices: dict[str, float],
        min_notional: float = 1.0,
    ) -> None:
        self._policy = policy
        self._data = data
        self._signals = signals
        self._risk_gate = risk_gate
        self._broker = broker
        self._state_store = state_store
        self._config = config
        self._prices = prices
        self._min_notional = min_notional
        self._state = state_store.load() or EngineState()
        self._reconciler = Reconciler()

    @property
    def state(self) -> EngineState:
        return self._state

    def _refresh_prices_and_history(self, now: datetime) -> dict[str, list[Bar]]:
        bars = self._data.get_bars(self._config.universe, _EPOCH, now, self._config.decision_freq)
        history: dict[str, list[Bar]] = {symbol: [] for symbol in self._config.universe}
        for bar in bars:
            if bar.symbol in history and bar.ts <= now:
                history[bar.symbol].append(bar)
        for symbol, symbol_bars in history.items():
            if symbol_bars:
                self._prices[symbol] = symbol_bars[-1].close
        return history

    def step(self, now: datetime) -> StepReport:
        try:
            history = self._refresh_prices_and_history(now)
            portfolio = self._broker.get_positions()

            if self._state.day_start_equity is None:
                self._state.day_start_equity = portfolio.equity
            self._risk_gate.set_day_start_equity(self._state.day_start_equity)

            signals = (
                self._signals.signals_as_of(now, self._config.universe)
                if self._signals is not None
                else []
            )
            ctx = DecisionContext(as_of=now, bars=history, signals=signals, portfolio=portfolio)
            target = self._policy.decide(ctx)
            orders = weights_to_orders(
                target, portfolio, self._prices, min_notional=self._min_notional
            )
            decision = self._risk_gate.check(orders, portfolio)

            submitted_set = set(self._state.submitted_order_ids)
            newly: list[str] = []
            for order in decision.approved:
                if order.client_order_id in submitted_set:
                    continue  # 幂等：已提交过（重放/重启）不重复下单
                self._broker.submit(order)
                submitted_set.add(order.client_order_id)
                newly.append(order.client_order_id)

            updated = self._broker.get_positions()
            report = self._reconciler.reconcile(self._broker, self._state)

            self._state.positions = dict(updated.positions)
            self._state.cash = updated.cash
            self._state.submitted_order_ids = sorted(submitted_set)
            self._state.last_ts = now
            self._state_store.save(self._state)

            return StepReport(
                ts=now,
                target_weights=dict(target.weights),
                submitted_order_ids=newly,
                denied=decision.denied,
                reconcile_ok=report.ok,
            )
        except Exception as error:  # noqa: BLE001 — 主循环必须安全降级，不得整体崩溃
            return StepReport(ts=now, degraded=True, error=str(error))

    def run(self, timestamps: list[datetime]) -> list[StepReport]:
        return [self.step(ts) for ts in timestamps]
