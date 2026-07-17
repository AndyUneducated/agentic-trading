from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from atrading.backtest import BacktestRunner, CostModel
from atrading.config.settings import Settings
from atrading.core.signal_schema import SignalSchemaV1
from atrading.core.strategy_config import StrategyConfig
from atrading.core.types import Bar
from atrading.data import InMemoryDataSource
from atrading.decision import PassthroughSizer, RulesDecisionPolicy
from atrading.execution import FileStateStore, SimulatedBroker, TradingLoop
from atrading.risk import PreTradeRiskGate, RiskLimits
from atrading.signals import LLMSignalSource


def _series(symbol: str, closes: list[float]) -> list[Bar]:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        Bar(symbol=symbol, ts=base + timedelta(days=i), open=c, high=c, low=c, close=c, volume=1.0)
        for i, c in enumerate(closes)
    ]


def _signal(symbol: str, sentiment: float) -> SignalSchemaV1:
    return SignalSchemaV1(
        symbol=symbol,
        as_of=datetime(2026, 1, 1, tzinfo=UTC),
        sentiment=sentiment,
        horizon_days=5,
        confidence=0.9,
        model_version="offline-keyword-v1",
        prompt_version="v1",
        rationale="t",
    )


def _generous_limits() -> RiskLimits:
    return RiskLimits(
        max_position_per_name=60_000.0,
        max_gross_exposure=100_000.0,
        max_notional_per_order=50_000.0,
        max_orders_per_interval=5,
        daily_loss_limit=0.5,
    )


def _config() -> StrategyConfig:
    return StrategyConfig(name="m5", universe=["AAA"], decision_freq="daily")


def test_no_order_bypasses_risk_gate(tmp_path: Path) -> None:
    prices: dict[str, float] = {}
    broker = SimulatedBroker(prices, starting_cash=100_000.0)
    config = _config()
    tiny_limits = _generous_limits().model_copy(update={"max_notional_per_order": 1_000.0})
    gate = PreTradeRiskGate(tiny_limits, Settings(), prices)
    loop = TradingLoop(
        policy=RulesDecisionPolicy(config, PassthroughSizer(config)),
        data=InMemoryDataSource(_series("AAA", [100.0, 101.0])),
        signals=LLMSignalSource([_signal("AAA", 0.8)]),
        risk_gate=gate,
        broker=broker,
        state_store=FileStateStore(tmp_path / "s.json"),
        config=config,
        prices=prices,
    )
    report = loop.step(datetime(2026, 1, 1, tzinfo=UTC))
    assert report.denied  # 订单被风控拒绝
    assert broker.get_positions().positions == {}  # 没有任何订单绕过风控到达 broker


def test_safe_degrade_on_data_error(tmp_path: Path) -> None:
    class BrokenData:
        def get_bars(self, symbols, start, end, freq):  # type: ignore[no-untyped-def]
            msg = "data source down"
            raise RuntimeError(msg)

    prices: dict[str, float] = {}
    config = _config()
    loop = TradingLoop(
        policy=RulesDecisionPolicy(config, PassthroughSizer(config)),
        data=BrokenData(),
        signals=None,
        risk_gate=PreTradeRiskGate(_generous_limits(), Settings(), prices),
        broker=SimulatedBroker(prices, starting_cash=100_000.0),
        state_store=FileStateStore(tmp_path / "s.json"),
        config=config,
        prices=prices,
    )
    report = loop.step(datetime(2026, 1, 1, tzinfo=UTC))
    assert report.degraded
    assert report.error is not None


def test_crash_recovery_no_duplicate_orders(tmp_path: Path) -> None:
    prices: dict[str, float] = {}
    broker = SimulatedBroker(prices, starting_cash=100_000.0)
    store = FileStateStore(tmp_path / "s.json")
    config = _config()
    data = InMemoryDataSource(_series("AAA", [100.0, 101.0]))
    signals = LLMSignalSource([_signal("AAA", 0.8)])
    day = datetime(2026, 1, 1, tzinfo=UTC)

    loop1 = TradingLoop(
        policy=RulesDecisionPolicy(config, PassthroughSizer(config)),
        data=data,
        signals=signals,
        risk_gate=PreTradeRiskGate(_generous_limits(), Settings(), prices),
        broker=broker,
        state_store=store,
        config=config,
        prices=prices,
    )
    loop1.step(day)
    fills_after_first = len(broker.get_fills(datetime(1970, 1, 1, tzinfo=UTC)))
    assert fills_after_first == 1
    assert store.load() is not None  # 状态已持久化

    # 模拟重启：新 loop 从持久化状态恢复，复用同一 broker。
    loop2 = TradingLoop(
        policy=RulesDecisionPolicy(config, PassthroughSizer(config)),
        data=data,
        signals=signals,
        risk_gate=PreTradeRiskGate(_generous_limits(), Settings(), prices),
        broker=broker,
        state_store=store,
        config=config,
        prices=prices,
    )
    report2 = loop2.step(day)
    assert report2.submitted_order_ids == []  # 幂等：不重复下单
    assert len(broker.get_fills(datetime(1970, 1, 1, tzinfo=UTC))) == 1  # 无重复成交


def test_reconcile_ok_on_normal_trading_step(tmp_path: Path) -> None:
    # 回归：自己刚提交并成交的订单不得被误判为"意外成交"（reconcile_ok 应为 True）。
    prices: dict[str, float] = {}
    broker = SimulatedBroker(prices, starting_cash=100_000.0)
    config = _config()
    loop = TradingLoop(
        policy=RulesDecisionPolicy(config, PassthroughSizer(config)),
        data=InMemoryDataSource(_series("AAA", [100.0, 101.0])),
        signals=LLMSignalSource([_signal("AAA", 0.8)]),
        risk_gate=PreTradeRiskGate(_generous_limits(), Settings(), prices),
        broker=broker,
        state_store=FileStateStore(tmp_path / "s.json"),
        config=config,
        prices=prices,
    )
    report = loop.step(datetime(2026, 1, 1, tzinfo=UTC))
    assert report.submitted_order_ids  # 确有下单
    assert report.reconcile_ok  # 且对账通过（无误报）


def test_reconcile_detects_ghost_fill_through_loop(tmp_path: Path) -> None:
    from atrading.core.types import Fill

    prices: dict[str, float] = {}
    broker = SimulatedBroker(prices, starting_cash=100_000.0)
    config = _config()
    # 券商侧"凭空多出"一笔我们从未提交的成交。
    broker.inject_fill(
        Fill(
            client_order_id="ghost",
            symbol="AAA",
            qty=1.0,
            price=100.0,
            ts=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    loop = TradingLoop(
        policy=RulesDecisionPolicy(config, PassthroughSizer(config)),
        data=InMemoryDataSource(_series("AAA", [100.0, 101.0])),
        signals=None,
        risk_gate=PreTradeRiskGate(_generous_limits(), Settings(), prices),
        broker=broker,
        state_store=FileStateStore(tmp_path / "s.json"),
        config=config,
        prices=prices,
    )
    report = loop.step(datetime(2026, 1, 1, tzinfo=UTC))
    assert not report.reconcile_ok  # 意外成交被检出


def test_backtest_live_parity_same_target_weights(tmp_path: Path) -> None:
    config = StrategyConfig(name="parity", universe=["AAA", "BBB"], decision_freq="daily")
    bars = _series("AAA", [100.0, 102.0, 104.0, 106.0]) + _series("BBB", [100.0, 99.0, 98.0, 97.0])
    data = InMemoryDataSource(bars)
    signals = LLMSignalSource([_signal("AAA", 0.8), _signal("BBB", -0.8)])
    policy = RulesDecisionPolicy(config, PassthroughSizer(config))

    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 1, 4, tzinfo=UTC)
    bt = BacktestRunner(
        policy=policy,
        data=data,
        costs=CostModel(commission_bps=0.0, slippage_bps=0.0),
        config=config,
        signals=signals,
    ).run(start, end)
    bt_weights = [dict(tw.weights) for tw in bt.target_weights]

    prices: dict[str, float] = {}
    timestamps = [start + timedelta(days=i) for i in range(4)]
    loop = TradingLoop(
        policy=policy,
        data=data,
        signals=signals,
        risk_gate=PreTradeRiskGate(_generous_limits(), Settings(), prices),
        broker=SimulatedBroker(prices, starting_cash=100_000.0),
        state_store=FileStateStore(tmp_path / "s.json"),
        config=config,
        prices=prices,
    )
    reports = loop.run(timestamps)
    assert all(not r.degraded for r in reports)
    loop_weights = [r.target_weights for r in reports]

    # 同一 DecisionPolicy、同输入 → 回测与实盘循环产出一致的目标权重（ADR-0003）。
    assert bt_weights == loop_weights
