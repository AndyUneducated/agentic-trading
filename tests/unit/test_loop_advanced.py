"""TradingLoop 进阶接线测试：RealisticBroker 撮合、Tracer span、Clock 驱动 tick。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from atrading.clock import ManualClock
from atrading.config.settings import Settings
from atrading.core.signal_schema import SignalSchemaV1
from atrading.core.strategy_config import StrategyConfig
from atrading.core.types import Bar
from atrading.data import InMemoryDataSource
from atrading.decision import PassthroughSizer, RulesDecisionPolicy
from atrading.execution import FileStateStore, RealisticBroker, SimulatedBroker, TradingLoop
from atrading.monitoring import Tracer
from atrading.risk import PreTradeRiskGate, RiskLimits
from atrading.signals import LLMSignalSource

_DAY = datetime(2026, 1, 1, tzinfo=UTC)


def _series(symbol: str, closes: list[float]) -> list[Bar]:
    return [
        Bar(symbol=symbol, ts=_DAY + timedelta(days=i), open=c, high=c, low=c, close=c, volume=1e9)
        for i, c in enumerate(closes)
    ]


def _signal(symbol: str, sentiment: float) -> SignalSchemaV1:
    return SignalSchemaV1(
        symbol=symbol,
        as_of=_DAY,
        sentiment=sentiment,
        horizon_days=5,
        confidence=0.9,
        model_version="offline-keyword-v1",
        prompt_version="v1",
        rationale="t",
    )


def _limits() -> RiskLimits:
    return RiskLimits(
        max_position_per_name=60_000.0,
        max_gross_exposure=100_000.0,
        max_notional_per_order=50_000.0,
        max_orders_per_interval=5,
        daily_loss_limit=0.5,
    )


def _config() -> StrategyConfig:
    return StrategyConfig(name="adv", universe=["AAA"], decision_freq="daily")


def _build(
    broker: RealisticBroker | SimulatedBroker,
    prices: dict[str, float],
    tmp_path: Path,
    *,
    tracer: Tracer | None = None,
    clock: ManualClock | None = None,
) -> TradingLoop:
    config = _config()
    return TradingLoop(
        policy=RulesDecisionPolicy(config, PassthroughSizer(config)),
        data=InMemoryDataSource(_series("AAA", [100.0, 101.0])),
        signals=LLMSignalSource([_signal("AAA", 0.8)]),
        risk_gate=PreTradeRiskGate(_limits(), Settings(), prices),
        broker=broker,
        state_store=FileStateStore(tmp_path / "s.json"),
        config=config,
        prices=prices,
        tracer=tracer,
        clock=clock,
    )


def test_realistic_broker_fills_through_loop(tmp_path: Path) -> None:
    prices: dict[str, float] = {}
    broker = RealisticBroker(prices, starting_cash=100_000.0)  # 零延迟、满参与
    loop = _build(broker, prices, tmp_path)
    report = loop.step(_DAY)
    assert report.submitted_order_ids  # 下单
    assert broker.get_positions().positions.get("AAA", 0.0) > 0.0  # advance 已撮合成交


def test_tracer_records_phase_spans(tmp_path: Path) -> None:
    prices: dict[str, float] = {}
    tracer = Tracer()
    loop = _build(SimulatedBroker(prices, starting_cash=100_000.0), prices, tmp_path, tracer=tracer)
    loop.step(_DAY)
    names = {span.name for span in tracer.finished()}
    assert {"step", "observe", "signals", "decide", "risk", "execute", "reconcile"} <= names


def test_tick_uses_injected_clock(tmp_path: Path) -> None:
    prices: dict[str, float] = {}
    clock = ManualClock(_DAY)
    loop = _build(SimulatedBroker(prices, starting_cash=100_000.0), prices, tmp_path, clock=clock)
    report = loop.tick()
    assert report.ts == _DAY
    assert not report.degraded
