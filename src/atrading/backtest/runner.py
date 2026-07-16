"""确定性回测运行器（参考引擎）。

按 decision_freq 逐期重放：构造 PIT 的 DecisionContext → 调用统一 DecisionPolicy →
得到目标权重 → 按换手计成本 → 组合按资产收益演进。全程确定性、无未来函数。

这是 ADR-0002 中"藏在接口后的引擎"的参考实现：决策语义与 PIT/成本完全受我们控制；
后续可在不改动 DecisionPolicy 与调用方的前提下替换为 vectorbt/bt。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import AwareDatetime, BaseModel, Field

from atrading.backtest.costs import CostModel
from atrading.core.interfaces import DataSource, DecisionContext, DecisionPolicy, SignalSource
from atrading.core.manifest import RunManifest
from atrading.core.strategy_config import StrategyConfig
from atrading.core.types import Bar, PortfolioState, Signal, TargetWeights


class EquityPoint(BaseModel):
    ts: AwareDatetime
    equity: float


class BacktestResult(BaseModel):
    manifest: RunManifest
    initial_cash: float
    final_equity: float
    equity_curve: list[EquityPoint] = Field(default_factory=list)
    target_weights: list[TargetWeights] = Field(default_factory=list)

    def equity_values(self) -> list[float]:
        return [point.equity for point in self.equity_curve]


class BacktestRunner:
    def __init__(
        self,
        policy: DecisionPolicy,
        data: DataSource,
        costs: CostModel,
        config: StrategyConfig,
        signals: SignalSource | None = None,
        seed: int = 0,
        initial_cash: float = 100_000.0,
    ) -> None:
        self._policy = policy
        self._data = data
        self._costs = costs
        self._config = config
        self._signals = signals
        self._seed = seed
        self._initial_cash = initial_cash

    def run(self, start: datetime, end: datetime) -> BacktestResult:
        universe = self._config.universe
        bars = list(self._data.get_bars(universe, start, end, self._config.decision_freq))

        bar_index: dict[str, dict[datetime, Bar]] = {s: {} for s in universe}
        close_by_ts: dict[datetime, dict[str, float]] = {}
        for bar in bars:
            if bar.symbol not in bar_index:
                continue
            bar_index[bar.symbol][bar.ts] = bar
            close_by_ts.setdefault(bar.ts, {})[bar.symbol] = bar.close
        dates = sorted(close_by_ts)

        history: dict[str, list[Bar]] = {s: [] for s in universe}
        prev_weights: dict[str, float] = {}
        prev_close: dict[str, float] = {}
        equity = self._initial_cash
        equity_curve: list[EquityPoint] = []
        target_log: list[TargetWeights] = []

        for ts in dates:
            close_now = close_by_ts[ts]
            for symbol in universe:
                todays_bar = bar_index[symbol].get(ts)
                if todays_bar is not None:
                    history[symbol].append(todays_bar)

            if prev_close:
                ret = 0.0
                for symbol, weight in prev_weights.items():
                    last = prev_close.get(symbol)
                    now = close_now.get(symbol)
                    if last is not None and now is not None and last > 0:
                        ret += weight * (now / last - 1.0)
                equity *= 1.0 + ret

            portfolio = self._portfolio_state(ts, prev_weights, close_now, equity)
            ctx = DecisionContext(
                as_of=ts,
                bars={s: list(history[s]) for s in universe},
                signals=self._signals_as_of(ts, universe),
                portfolio=portfolio,
            )
            target = self._policy.decide(ctx)

            turnover = self._turnover(prev_weights, target.weights)
            equity *= 1.0 - self._costs.cost_fraction(turnover)

            equity_curve.append(EquityPoint(ts=ts, equity=equity))
            target_log.append(target)
            prev_weights = dict(target.weights)
            prev_close = close_now

        return BacktestResult(
            manifest=RunManifest(seed=self._seed, params={"strategy": self._config.name}),
            initial_cash=self._initial_cash,
            final_equity=equity_curve[-1].equity if equity_curve else self._initial_cash,
            equity_curve=equity_curve,
            target_weights=target_log,
        )

    def _signals_as_of(self, ts: datetime, universe: list[str]) -> list[Signal]:
        if self._signals is None:
            return []
        return self._signals.signals_as_of(ts, universe)

    @staticmethod
    def _turnover(prev: dict[str, float], new: dict[str, float]) -> float:
        symbols = set(prev) | set(new)
        return sum(abs(new.get(s, 0.0) - prev.get(s, 0.0)) for s in symbols)

    @staticmethod
    def _portfolio_state(
        ts: datetime,
        weights: dict[str, float],
        close_now: dict[str, float],
        equity: float,
    ) -> PortfolioState:
        positions: dict[str, float] = {}
        for symbol, weight in weights.items():
            price = close_now.get(symbol)
            if price is not None and price > 0:
                positions[symbol] = weight * equity / price
        invested = sum(positions[s] * close_now[s] for s in positions)
        return PortfolioState(
            ts=ts,
            cash=equity - invested,
            positions=positions,
            equity=equity,
        )
