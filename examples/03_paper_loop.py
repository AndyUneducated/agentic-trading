"""示例 03：完整模拟盘闭环（信号 → 决策 → 风控 → 执行 → 对账）。

uv run python examples/03_paper_loop.py
"""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from atrading.config.settings import Settings
from atrading.core.signal_schema import SignalSchemaV1
from atrading.core.strategy_config import StrategyConfig
from atrading.core.types import Bar
from atrading.data import InMemoryDataSource
from atrading.decision import PassthroughSizer, RulesDecisionPolicy
from atrading.execution import FileStateStore, SimulatedBroker, TradingLoop
from atrading.risk import PreTradeRiskGate, RiskLimits
from atrading.signals import LLMSignalSource


def main() -> None:
    config = StrategyConfig(name="demo", universe=["AAA"], decision_freq="daily")
    prices: dict[str, float] = {}  # 由 loop 持续更新（broker / 风控共享同一引用）
    days = [datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=i) for i in range(3)]
    bars = [
        Bar(symbol="AAA", ts=d, open=p, high=p, low=p, close=p, volume=1.0)
        for d, p in zip(days, [100.0, 101.0, 102.0], strict=True)
    ]
    signal = SignalSchemaV1(
        symbol="AAA",
        as_of=days[0],
        sentiment=0.8,
        horizon_days=5,
        confidence=0.9,
        model_version="offline-keyword-v1",
        prompt_version="v1",
        rationale="demo",
    )

    limits = RiskLimits(
        max_position_per_name=60_000,
        max_gross_exposure=100_000,
        max_notional_per_order=50_000,
        max_orders_per_interval=5,
        daily_loss_limit=0.2,
    )
    with tempfile.TemporaryDirectory() as tmp:
        loop = TradingLoop(
            policy=RulesDecisionPolicy(config, PassthroughSizer(config)),
            data=InMemoryDataSource(bars),
            signals=LLMSignalSource([signal]),
            risk_gate=PreTradeRiskGate(limits, Settings(), prices),  # 默认 paper
            broker=SimulatedBroker(prices, starting_cash=100_000.0),
            state_store=FileStateStore(Path(tmp) / "state.json"),  # 崩溃恢复
            config=config,
            prices=prices,
        )
        reports = loop.run(days)

    for report in reports:
        print(f"{report.ts.date()} 提交 {report.submitted_order_ids} 对账OK={report.reconcile_ok}")
    print("最终持仓:", loop.state.positions)


if __name__ == "__main__":
    main()
