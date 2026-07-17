"""集成测试：从配置经组合根装配 → 端到端跑回测 / 模拟盘闭环。"""

from __future__ import annotations

from pathlib import Path

from atrading.app import build_backtest, build_paper_loop
from atrading.cli import synthetic_bars
from atrading.config import RunConfig, Settings
from atrading.core.signal_schema import SignalSchemaV1
from atrading.core.strategy_config import StrategyConfig
from atrading.data import InMemoryDataSource
from atrading.execution import SimulatedBroker, SQLiteStateStore
from atrading.monitoring import MetricsRegistry
from atrading.signals import LLMSignalSource


def test_build_backtest_runs_end_to_end() -> None:
    config = StrategyConfig(name="t", universe=["AAA", "BBB"], decision_freq="daily")
    bars = synthetic_bars(["AAA", "BBB"], days=30, seed=1)
    runner = build_backtest(config=config, data=InMemoryDataSource(bars), policy="equal_weight")
    result = runner.run(bars[0].ts, bars[-1].ts)
    assert len(result.equity_values()) == 30


def test_build_paper_loop_end_to_end(tmp_path: Path) -> None:
    run_config = RunConfig.from_yaml("configs/paper.yaml")
    strategy = run_config.load_strategy()
    bars = synthetic_bars(strategy.universe, days=15, seed=2)
    prices: dict[str, float] = {}
    first_day = bars[0].ts
    signals = LLMSignalSource(
        [
            SignalSchemaV1(
                symbol=symbol,
                as_of=first_day,
                sentiment=0.5,
                horizon_days=5,
                confidence=0.9,
                model_version="offline-demo",
                prompt_version="v1",
                rationale="demo",
            )
            for symbol in strategy.universe
        ]
    )
    metrics = MetricsRegistry()
    loop = build_paper_loop(
        run_config=run_config,
        settings=Settings(),
        data=InMemoryDataSource(bars),
        prices=prices,
        state_store=SQLiteStateStore(tmp_path / "state.db", namespace=strategy.name),
        broker=SimulatedBroker(prices),
        signals=signals,
        metrics=metrics,
    )
    reports = loop.run(sorted({bar.ts for bar in bars}))

    assert len(reports) == 15
    assert not any(report.degraded for report in reports)
    assert "atrading_steps_total" in metrics.render()
    # 组合根装配的风控限额来自 configs/paper.yaml（配置化，非硬编码）
    assert loop.state.last_ts is not None
