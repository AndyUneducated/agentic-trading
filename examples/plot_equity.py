"""示例：生成权益曲线图（策略 vs 买入持有基线）→ docs/assets/equity_curve.png。

需要 viz 附加依赖：

    uv run --extra viz python examples/plot_equity.py

合成数据仅供演示，**不构成任何真实 alpha 证据**。
"""

from __future__ import annotations

from pathlib import Path

from atrading.backtest import (
    BacktestRunner,
    CostModel,
    EqualWeightPolicy,
    SingleAssetBuyHoldPolicy,
)
from atrading.cli import synthetic_bars
from atrading.core.strategy_config import StrategyConfig
from atrading.data import InMemoryDataSource


def main() -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    universe = ["AAA", "BBB", "CCC"]
    bars = synthetic_bars(universe, days=252, seed=7)
    data = InMemoryDataSource(bars)
    costs = CostModel(commission_bps=1.0, slippage_bps=5.0)
    start, end = bars[0].ts, bars[-1].ts

    strat = BacktestRunner(
        EqualWeightPolicy(universe),
        data,
        costs,
        StrategyConfig(name="equal_weight", universe=universe, decision_freq="daily"),
    ).run(start, end)
    bh = BacktestRunner(
        SingleAssetBuyHoldPolicy("AAA"),
        data,
        costs,
        StrategyConfig(name="buy_hold", universe=["AAA"], decision_freq="daily"),
    ).run(start, end)

    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot([p.ts for p in strat.equity_curve], strat.equity_values(), label="EqualWeight strategy")
    ax.plot(
        [p.ts for p in bh.equity_curve],
        bh.equity_values(),
        label="Buy & Hold baseline",
        linestyle="--",
    )
    ax.set_title("Agentic Trading - offline backtest equity (synthetic demo data)")
    ax.set_ylabel("Equity")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()

    out = Path("docs/assets/equity_curve.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=120)
    print(f"saved {out}")


if __name__ == "__main__":
    main()
