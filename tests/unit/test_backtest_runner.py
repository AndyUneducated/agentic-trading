"""回测运行器：PIT 正确性、可复现性、成本单调性。"""

from __future__ import annotations

from datetime import UTC, datetime

from atrading.backtest import BacktestRunner, ConstantWeightPolicy, CostModel
from atrading.core.interfaces import DecisionContext
from atrading.core.strategy_config import StrategyConfig
from atrading.core.types import Bar, TargetWeights
from atrading.data import InMemoryDataSource


def _bar(symbol: str, day: int, close: float) -> Bar:
    ts = datetime(2026, 1, day, tzinfo=UTC)
    return Bar(symbol=symbol, ts=ts, open=close, high=close, low=close, close=close, volume=1.0)


def _bars() -> list[Bar]:
    return [
        _bar("A", 1, 100.0),
        _bar("A", 2, 110.0),
        _bar("A", 3, 121.0),
        _bar("A", 4, 121.0),
    ]


def _config() -> StrategyConfig:
    return StrategyConfig(name="t", universe=["A"], decision_freq="daily")


def _run(costs: CostModel) -> float:
    runner = BacktestRunner(
        policy=ConstantWeightPolicy({"A": 1.0}),
        data=InMemoryDataSource(_bars()),
        costs=costs,
        config=_config(),
        initial_cash=100_000.0,
    )
    result = runner.run(datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 4, tzinfo=UTC))
    return result.final_equity


def test_reproducible_same_inputs_same_output() -> None:
    zero = CostModel(commission_bps=0.0, slippage_bps=0.0)
    a = _run(zero)
    b = _run(zero)
    assert a == b


def test_higher_costs_reduce_equity() -> None:
    low = _run(CostModel(commission_bps=1.0, slippage_bps=1.0))
    high = _run(CostModel(commission_bps=50.0, slippage_bps=50.0))
    assert high < low


def test_no_lookahead_in_decision_context() -> None:
    violations: list[tuple[datetime, datetime]] = []

    class PitSpyPolicy:
        def decide(self, ctx: DecisionContext) -> TargetWeights:
            for symbol_bars in ctx.bars.values():
                for bar in symbol_bars:
                    if bar.ts > ctx.as_of:
                        violations.append((bar.ts, ctx.as_of))
            return TargetWeights(as_of=ctx.as_of, weights={"A": 1.0})

    runner = BacktestRunner(
        policy=PitSpyPolicy(),
        data=InMemoryDataSource(_bars()),
        costs=CostModel(commission_bps=0.0, slippage_bps=0.0),
        config=_config(),
    )
    runner.run(datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 4, tzinfo=UTC))
    assert violations == []
