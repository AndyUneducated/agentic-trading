"""示例 07：组合根装配（config 驱动 + 配置化风控 + SQLite 状态）。

安全关键的风控限额来自 configs/paper.yaml（纳入版本控制，非硬编码）；`app.build_paper_loop`
按配置一处装配决策/风控/执行——这正是 `atrading paper` 走的路径。

uv run python examples/07_composition_root.py
"""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from atrading.app import build_paper_loop
from atrading.config import RunConfig, Settings
from atrading.core.signal_schema import SignalSchemaV1
from atrading.core.types import Bar
from atrading.data import InMemoryDataSource
from atrading.execution import SQLiteStateStore
from atrading.signals import LLMSignalSource


def main() -> None:
    run_config = RunConfig.from_yaml("configs/paper.yaml")  # 策略路径 + 日志 + 风控限额
    strategy = run_config.load_strategy()
    print(f"策略={strategy.name} 标的数={len(strategy.universe)}")
    print(f"配置化风控: 单笔名义上限={run_config.risk.max_notional_per_order}")

    days = [datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=i) for i in range(5)]
    bars = [
        Bar(symbol=symbol, ts=d, open=100.0, high=100.0, low=100.0, close=100.0, volume=1e9)
        for symbol in strategy.universe
        for d in days
    ]
    # 每标的一条正面信号（as_of 首日）驱动闭环产生交易——仅演示。
    signals = LLMSignalSource(
        [
            SignalSchemaV1(
                symbol=symbol,
                as_of=days[0],
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

    prices: dict[str, float] = {}
    with tempfile.TemporaryDirectory() as tmp:
        loop = build_paper_loop(
            run_config=run_config,
            settings=Settings(),
            data=InMemoryDataSource(bars),
            prices=prices,
            state_store=SQLiteStateStore(Path(tmp) / "atrading.db", namespace=strategy.name),
            signals=signals,
        )
        reports = loop.run(days)

    submitted = sum(len(r.submitted_order_ids) for r in reports)
    denied = sum(len(r.denied) for r in reports)
    print(f"步数={len(reports)} 提交={submitted} 风控拒单={denied}")
    print("最终持仓标的数:", len(loop.state.positions))


if __name__ == "__main__":
    main()
