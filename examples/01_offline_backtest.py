"""示例 01：离线确定性回测（零依赖数据）。

uv run python examples/01_offline_backtest.py
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from atrading.backtest import BacktestRunner, CostModel, EqualWeightPolicy
from atrading.core.strategy_config import StrategyConfig
from atrading.core.types import Bar
from atrading.data import InMemoryDataSource
from atrading.eval import max_drawdown, returns_from_equity, sharpe, total_return


def main() -> None:
    universe = ["AAA", "BBB"]
    start = datetime(2026, 1, 1, tzinfo=UTC)
    series = {"AAA": [100.0, 102.0, 105.0, 108.0], "BBB": [50.0, 49.0, 51.0, 53.0]}
    bars = [
        Bar(symbol=symbol, ts=start + timedelta(days=d), open=p, high=p, low=p, close=p, volume=1.0)
        for symbol, prices in series.items()
        for d, p in enumerate(prices)
    ]

    config = StrategyConfig(name="demo", universe=universe, decision_freq="daily")
    result = BacktestRunner(
        policy=EqualWeightPolicy(universe),
        data=InMemoryDataSource(bars),
        costs=CostModel(commission_bps=1.0, slippage_bps=5.0),
        config=config,
    ).run(start, start + timedelta(days=3))

    equity = result.equity_values()
    print("权益曲线:", [round(e, 2) for e in equity])
    print(
        f"总收益 {total_return(equity):+.2%} | "
        f"最大回撤 {max_drawdown(equity):.2%} | "
        f"Sharpe {sharpe(returns_from_equity(equity)):.2f}"
    )


if __name__ == "__main__":
    main()
