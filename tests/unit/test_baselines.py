from __future__ import annotations

from datetime import UTC, datetime, timedelta

from atrading.backtest import CostModel
from atrading.core.strategy_config import StrategyConfig
from atrading.core.types import Bar
from atrading.data import InMemoryDataSource
from atrading.eval import run_baselines


def _series(symbol: str, closes: list[float]) -> list[Bar]:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        Bar(
            symbol=symbol,
            ts=base + timedelta(days=i),
            open=c,
            high=c,
            low=c,
            close=c,
            volume=1.0,
        )
        for i, c in enumerate(closes)
    ]


def test_run_baselines_returns_three_and_zero_is_flat() -> None:
    up = [100.0 + i for i in range(20)]
    down = [100.0 - i * 0.3 for i in range(20)]
    data = InMemoryDataSource(_series("AAA", up) + _series("BBB", down))
    config = StrategyConfig(name="b", universe=["AAA", "BBB"], decision_freq="daily")

    results = run_baselines(
        data=data,
        config=config,
        costs=CostModel(commission_bps=0.0, slippage_bps=0.0),
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 1, 20, tzinfo=UTC),
        initial_cash=100_000.0,
    )
    assert set(results) == {"zero", "price_only", "buy_hold"}

    zero_equity = results["zero"].equity_values()
    assert all(abs(v - 100_000.0) < 1e-9 for v in zero_equity)  # 全现金恒定
