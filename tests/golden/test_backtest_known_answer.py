"""Golden 已知答案回归：手算权益 vs 运行器输出。

若数值漂移，说明回测账务被无意改动——这是策略可信度的地基。
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atrading.backtest import BacktestRunner, ConstantWeightPolicy, CostModel
from atrading.core.strategy_config import StrategyConfig
from atrading.core.types import Bar
from atrading.data import InMemoryDataSource


def _bar(symbol: str, day: int, close: float) -> Bar:
    ts = datetime(2026, 1, day, tzinfo=UTC)
    return Bar(symbol=symbol, ts=ts, open=close, high=close, low=close, close=close, volume=1.0)


@pytest.mark.golden
def test_two_asset_constant_weight_known_answer() -> None:
    # A: +10%/日；B: 持平。50/50 每日再平衡，零成本。
    bars = [
        _bar("A", 1, 100.0),
        _bar("A", 2, 110.0),
        _bar("A", 3, 121.0),
        _bar("B", 1, 100.0),
        _bar("B", 2, 100.0),
        _bar("B", 3, 100.0),
    ]
    config = StrategyConfig(name="golden", universe=["A", "B"], decision_freq="daily")
    runner = BacktestRunner(
        policy=ConstantWeightPolicy({"A": 0.5, "B": 0.5}),
        data=InMemoryDataSource(bars),
        costs=CostModel(commission_bps=0.0, slippage_bps=0.0),
        config=config,
        initial_cash=100_000.0,
    )
    result = runner.run(datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 3, tzinfo=UTC))

    values = result.equity_values()
    assert values == pytest.approx([100_000.0, 105_000.0, 110_250.0])
    assert result.final_equity == pytest.approx(110_250.0)
