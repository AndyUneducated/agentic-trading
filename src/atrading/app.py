"""组合根（composition root）：从配置集中装配可运行对象。

把"如何把各组件拼起来"收敛到一处，避免散落在测试/CLI/脚本里重复手工 wiring。
回测与模拟盘闭环共用同一 `DecisionPolicy`（ADR-0003 回测-实盘一致）。
"""

from __future__ import annotations

from atrading.backtest import BacktestRunner, CostModel
from atrading.config import RunConfig, Settings
from atrading.core.interfaces import Broker, Clock, DataSource, SignalSource
from atrading.core.strategy_config import StrategyConfig
from atrading.execution import SimulatedBroker, TradingLoop
from atrading.execution.state_store import StateStore
from atrading.monitoring import MetricsRegistry, Tracer
from atrading.registry import build_policy
from atrading.risk import PreTradeRiskGate


def build_backtest(
    *,
    config: StrategyConfig,
    data: DataSource,
    costs: CostModel | None = None,
    policy: str = "equal_weight",
    signals: SignalSource | None = None,
    seed: int = 0,
    initial_cash: float = 100_000.0,
) -> BacktestRunner:
    """按策略名 + 配置装配回测运行器。"""
    return BacktestRunner(
        policy=build_policy(policy, config),
        data=data,
        costs=costs or CostModel(),
        config=config,
        signals=signals,
        seed=seed,
        initial_cash=initial_cash,
    )


def build_paper_loop(
    *,
    run_config: RunConfig,
    settings: Settings,
    data: DataSource,
    prices: dict[str, float],
    state_store: StateStore,
    broker: Broker | None = None,
    signals: SignalSource | None = None,
    metrics: MetricsRegistry | None = None,
    tracer: Tracer | None = None,
    clock: Clock | None = None,
) -> TradingLoop:
    """从 RunConfig 装配完整模拟盘闭环：风控限额来自配置、决策走统一 rules 策略。"""
    strategy = run_config.load_strategy()
    return TradingLoop(
        policy=build_policy("rules", strategy),
        data=data,
        signals=signals,
        risk_gate=PreTradeRiskGate(run_config.risk, settings, prices),
        broker=broker or SimulatedBroker(prices),
        state_store=state_store,
        config=strategy,
        prices=prices,
        metrics=metrics,
        tracer=tracer,
        clock=clock,
    )
