"""基线策略经运行器端到端跑通（Edge 证伪对照）。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atrading.backtest import (
    BacktestRunner,
    CostModel,
    EqualWeightPolicy,
    PriceOnlyMomentumPolicy,
    SingleAssetBuyHoldPolicy,
)
from atrading.core.strategy_config import StrategyConfig
from atrading.core.types import Bar
from atrading.data import InMemoryDataSource


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


def test_single_asset_buy_hold_tracks_asset() -> None:
    closes = [100.0, 110.0, 121.0]
    runner = BacktestRunner(
        policy=SingleAssetBuyHoldPolicy("A"),
        data=InMemoryDataSource(_series("A", closes)),
        costs=CostModel(commission_bps=0.0, slippage_bps=0.0),
        config=StrategyConfig(name="bh", universe=["A"], decision_freq="daily"),
        initial_cash=100_000.0,
    )
    result = runner.run(datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 3, tzinfo=UTC))
    # 满仓单标的、零成本 → 权益与标的同步 +21%。
    assert result.final_equity == pytest.approx(100_000.0 * (121.0 / 100.0))


def test_equal_weight_and_momentum_run() -> None:
    up = [100.0 + i for i in range(30)]
    down = [100.0 - i * 0.5 for i in range(30)]
    bars = _series("UP", up) + _series("DOWN", down)
    config = StrategyConfig(name="mom", universe=["UP", "DOWN"], decision_freq="daily")
    data = InMemoryDataSource(bars)
    costs = CostModel(commission_bps=1.0, slippage_bps=1.0)
    start, end = datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 30, tzinfo=UTC)

    ew = BacktestRunner(EqualWeightPolicy(["UP", "DOWN"]), data, costs, config).run(start, end)
    mom = BacktestRunner(
        PriceOnlyMomentumPolicy(["UP", "DOWN"], lookback=5, max_weight=1.0), data, costs, config
    ).run(start, end)

    assert len(ew.equity_curve) == 30
    assert len(mom.equity_curve) == 30
    # 动量满仓做多上涨标的，应跑赢等权（等权被下跌标的拖累）。
    assert mom.final_equity > ew.final_equity
