from __future__ import annotations

from datetime import UTC, datetime, timedelta

from atrading.backtest import BacktestRunner, CostModel
from atrading.core.interfaces import DecisionContext
from atrading.core.signal_schema import SignalSchemaV1
from atrading.core.strategy_config import StrategyConfig
from atrading.core.types import Bar, TargetWeights
from atrading.data import InMemoryDataSource
from atrading.signals import LLMSignalSource


def _schema(symbol: str, day: int, sentiment: float) -> SignalSchemaV1:
    return SignalSchemaV1(
        symbol=symbol,
        as_of=datetime(2026, 1, day, tzinfo=UTC),
        sentiment=sentiment,
        horizon_days=5,
        confidence=0.8,
        model_version="offline-keyword-v1",
        prompt_version="v1",
        rationale="test",
    )


def test_signals_as_of_pit_and_symbol_filter() -> None:
    source = LLMSignalSource([_schema("AAA", 2, 0.5), _schema("BBB", 2, -0.5)])

    # 早于信号 as_of → 不可见（PIT）。
    assert source.signals_as_of(datetime(2026, 1, 1, tzinfo=UTC), ["AAA", "BBB"]) == []

    only_aaa = source.signals_as_of(datetime(2026, 1, 3, tzinfo=UTC), ["AAA"])
    assert [s.symbol for s in only_aaa] == ["AAA"]
    assert only_aaa[0].name == "sentiment"
    assert only_aaa[0].value == 0.5


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


class SentimentPolicy:
    """做多情绪为正的标的（读取 ctx.signals，演示 M4→M3 贯通）。"""

    def __init__(self, universe: list[str]) -> None:
        self._universe = universe

    def decide(self, ctx: DecisionContext) -> TargetWeights:
        latest: dict[str, float] = {}
        for signal in ctx.signals:
            if signal.name == "sentiment":
                latest[signal.symbol] = signal.value
        longs = [s for s in self._universe if latest.get(s, 0.0) > 0]
        if not longs:
            return TargetWeights(as_of=ctx.as_of, weights={})
        w = 1.0 / len(longs)
        return TargetWeights(as_of=ctx.as_of, weights={s: w for s in longs})


def test_llm_signals_flow_into_backtest() -> None:
    bars = _series("AAA", [100.0, 105.0, 110.0, 116.0]) + _series("BBB", [100.0, 98.0, 96.0, 94.0])
    source = LLMSignalSource([_schema("AAA", 1, 0.7), _schema("BBB", 1, -0.7)])
    config = StrategyConfig(name="sent", universe=["AAA", "BBB"], decision_freq="daily")

    result = BacktestRunner(
        policy=SentimentPolicy(["AAA", "BBB"]),
        data=InMemoryDataSource(bars),
        costs=CostModel(commission_bps=0.0, slippage_bps=0.0),
        config=config,
        signals=source,
    ).run(datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 4, tzinfo=UTC))

    # 全程做多上涨的 AAA、回避下跌的 BBB → 期末权益应上涨。
    assert result.final_equity > result.initial_cash
    assert len(result.equity_curve) == 4
