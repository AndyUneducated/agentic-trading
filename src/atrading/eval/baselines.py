"""基准策略：防"已被定价" / 防"只跑赢玩具"。

所有基准都经**同一回测引擎、同一成本模型**运行（可比性），产出 BacktestResult。
Edge 证伪要求策略同时优于：zero（现金）、price_only（纯价量）、buy_hold（买入持有）。
OSS 基线（封装开源框架产出）在 M6 接入。
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from atrading.backtest import (
    BacktestResult,
    BacktestRunner,
    ConstantWeightPolicy,
    CostModel,
    EqualWeightPolicy,
    PriceOnlyMomentumPolicy,
    SingleAssetBuyHoldPolicy,
)
from atrading.backtest.runner import EquityPoint
from atrading.core.interfaces import DataSource
from atrading.core.manifest import RunManifest
from atrading.core.strategy_config import StrategyConfig


class Baseline(Protocol):
    name: str

    def run(
        self,
        *,
        data: DataSource,
        config: StrategyConfig,
        costs: CostModel,
        start: datetime,
        end: datetime,
        initial_cash: float = 100_000.0,
    ) -> BacktestResult: ...


class ZeroBaseline:
    """全现金：权益恒定。任何策略都应至少跑赢现金。"""

    name = "zero"

    def run(
        self,
        *,
        data: DataSource,
        config: StrategyConfig,
        costs: CostModel,
        start: datetime,
        end: datetime,
        initial_cash: float = 100_000.0,
    ) -> BacktestResult:
        runner = BacktestRunner(
            policy=ConstantWeightPolicy({}),
            data=data,
            costs=costs,
            config=config,
            initial_cash=initial_cash,
        )
        return runner.run(start, end)


class PriceOnlyBaseline:
    """纯价量动量：LLM 信号必须优于它，否则只是复述已被定价的信息。"""

    name = "price_only"

    def __init__(self, lookback: int = 20, max_weight: float = 0.2) -> None:
        self._lookback = lookback
        self._max_weight = max_weight

    def run(
        self,
        *,
        data: DataSource,
        config: StrategyConfig,
        costs: CostModel,
        start: datetime,
        end: datetime,
        initial_cash: float = 100_000.0,
    ) -> BacktestResult:
        runner = BacktestRunner(
            policy=PriceOnlyMomentumPolicy(
                config.universe, lookback=self._lookback, max_weight=self._max_weight
            ),
            data=data,
            costs=costs,
            config=config,
            initial_cash=initial_cash,
        )
        return runner.run(start, end)


class BuyHoldBaseline:
    """买入持有：单标的（如 SPY/BTC）满仓，或全域等权。"""

    name = "buy_hold"

    def __init__(self, symbol: str | None = None) -> None:
        self._symbol = symbol

    def run(
        self,
        *,
        data: DataSource,
        config: StrategyConfig,
        costs: CostModel,
        start: datetime,
        end: datetime,
        initial_cash: float = 100_000.0,
    ) -> BacktestResult:
        policy = (
            SingleAssetBuyHoldPolicy(self._symbol)
            if self._symbol is not None
            else EqualWeightPolicy(config.universe)
        )
        runner = BacktestRunner(
            policy=policy,
            data=data,
            costs=costs,
            config=config,
            initial_cash=initial_cash,
        )
        return runner.run(start, end)


def oss_baseline_from_equity(
    name: str,
    timestamps: list[datetime],
    equity: list[float],
) -> BacktestResult:
    """把开源框架（TradingAgents/ai-hedge-fund/FinRL）在同区间同标的的**产出权益曲线**
    封装为 BacktestResult，作为"第三类基线"参与对照（M6 现实性校验）。

    离线：不在运行时依赖开源框架，只消费其导出的权益序列（遵守混合红线：其 LLM 决策
    不接我们的执行）。若要接入，把该框架跑出的 (ts, equity) 序列喂进来即可。
    """
    if len(timestamps) != len(equity):
        msg = "timestamps 与 equity 长度必须一致"
        raise ValueError(msg)
    if not equity:
        msg = "equity 不能为空"
        raise ValueError(msg)
    curve = [EquityPoint(ts=ts, equity=v) for ts, v in zip(timestamps, equity, strict=True)]
    return BacktestResult(
        manifest=RunManifest(seed=0, params={"oss_baseline": name}),
        initial_cash=equity[0],
        final_equity=equity[-1],
        equity_curve=curve,
    )


def run_baselines(
    *,
    data: DataSource,
    config: StrategyConfig,
    costs: CostModel,
    start: datetime,
    end: datetime,
    initial_cash: float = 100_000.0,
) -> dict[str, BacktestResult]:
    """跑标准三类基线，返回 {name: BacktestResult}。"""
    baselines: list[Baseline] = [ZeroBaseline(), PriceOnlyBaseline(), BuyHoldBaseline()]
    return {
        baseline.name: baseline.run(
            data=data,
            config=config,
            costs=costs,
            start=start,
            end=end,
            initial_cash=initial_cash,
        )
        for baseline in baselines
    }
