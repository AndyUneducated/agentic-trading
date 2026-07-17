"""交易主循环：observe → 信号 → 决策 → 风控门 → 执行 → 对账 → 持久化。

复用 M3 统一 DecisionPolicy（回测-实盘一致，ADR-0003）；环境差异隔离在 DataSource/
Broker/Clock。任何一步异常 → **安全降级**（本步不交易，记录），进入下一循环。
只提交 RiskGate.approved 的订单；幂等 client_order_id 支撑崩溃恢复不重复下单。
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from atrading.clock import SystemClock
from atrading.core.interfaces import (
    Broker,
    Clock,
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
from atrading.monitoring.metrics import MetricsRegistry
from atrading.monitoring.tracing import Tracer
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
        metrics: MetricsRegistry | None = None,
        tracer: Tracer | None = None,
        clock: Clock | None = None,
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
        self._metrics = metrics
        self._tracer = tracer
        self._clock: Clock = clock or SystemClock()
        self._state = state_store.load() or EngineState()
        self._reconciler = Reconciler()

    @property
    def state(self) -> EngineState:
        return self._state

    @contextmanager
    def _span(self, name: str) -> Iterator[None]:
        """可选 tracing：无 tracer 时零开销、不改行为。"""
        if self._tracer is None:
            yield
        else:
            with self._tracer.span(name):
                yield

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

    def tick(self) -> StepReport:
        """按注入的 Clock 取当前时刻跑一步（实时/调度场景的入口）。"""
        return self.step(self._clock.now())

    def step(self, now: datetime) -> StepReport:
        started = time.perf_counter()
        try:
            with self._span("step"):
                with self._span("observe"):
                    history = self._refresh_prices_and_history(now)
                    portfolio = self._broker.get_positions()

                # 日亏熔断需"每日"重置：跨自然日则以当日开盘权益为基线。
                is_new_day = self._state.last_ts is None or now.date() > self._state.last_ts.date()
                if self._state.day_start_equity is None or is_new_day:
                    self._state.day_start_equity = portfolio.equity
                self._risk_gate.set_day_start_equity(self._state.day_start_equity)

                with self._span("signals"):
                    signals = (
                        self._signals.signals_as_of(now, self._config.universe)
                        if self._signals is not None
                        else []
                    )
                with self._span("decide"):
                    ctx = DecisionContext(
                        as_of=now, bars=history, signals=signals, portfolio=portfolio
                    )
                    target = self._policy.decide(ctx)
                    orders = weights_to_orders(
                        target, portfolio, self._prices, min_notional=self._min_notional
                    )
                with self._span("risk"):
                    decision = self._risk_gate.check(orders, portfolio)

                with self._span("execute"):
                    submitted_set = set(self._state.submitted_order_ids)
                    newly: list[str] = []
                    for order in decision.approved:
                        if order.client_order_id in submitted_set:
                            continue  # 幂等：已提交过（重放/重启）不重复下单
                        self._broker.submit(order)
                        submitted_set.add(order.client_order_id)
                        newly.append(order.client_order_id)
                    # 推进撮合：即时成交 broker 为 no-op；高保真/真实 broker 在此产生成交。
                    self._broker.advance(now)

                updated = self._broker.get_positions()
                self._state.positions = dict(updated.positions)
                self._state.cash = updated.cash
                self._state.submitted_order_ids = sorted(submitted_set)
                self._state.last_ts = now
                with self._span("reconcile"):
                    # 先记录本步提交，再对账：自己刚成交的订单不应被误判为"意外成交"。
                    report = self._reconciler.reconcile(self._broker, self._state)
                self._state_store.save(self._state)

            self._record_ok(
                elapsed=time.perf_counter() - started,
                newly=newly,
                denied=decision.denied,
                mismatch=len(report.unexpected_fills) + len(report.position_mismatches),
                open_orders=len(self._broker.get_open_orders()),
            )
            return StepReport(
                ts=now,
                target_weights=dict(target.weights),
                submitted_order_ids=newly,
                denied=decision.denied,
                reconcile_ok=report.ok,
            )
        except Exception as error:  # noqa: BLE001 — 主循环必须安全降级，不得整体崩溃
            if self._metrics is not None:
                self._metrics.inc("atrading_steps_total", result="degraded")
                self._metrics.inc("atrading_step_errors_total", error_type=type(error).__name__)
            return StepReport(ts=now, degraded=True, error=str(error))

    def _record_ok(
        self,
        *,
        elapsed: float,
        newly: list[str],
        denied: list[tuple[Order, str]],
        mismatch: int,
        open_orders: int,
    ) -> None:
        if self._metrics is None:
            return
        self._metrics.observe("atrading_decision_seconds", elapsed)
        self._metrics.inc("atrading_steps_total", result="ok")
        if newly:
            self._metrics.inc("atrading_orders_submitted_total", float(len(newly)))
        for _order, reason in denied:
            self._metrics.inc("atrading_risk_denials_total", reason=reason)
        self._metrics.set("atrading_reconcile_mismatch", float(mismatch))
        self._metrics.set("atrading_open_orders", float(open_orders))

    def run(self, timestamps: list[datetime]) -> list[StepReport]:
        return [self.step(ts) for ts in timestamps]
