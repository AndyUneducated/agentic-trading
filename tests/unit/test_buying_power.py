"""回归：对**校验买力的券商**（真实/模拟，如 paper-trading-platform）不产生买力不足拒单。

我方 SimulatedBroker 不校验买力，会掩盖"买单先于卖单/满仓时买单超现金"的问题。这里用一个
最小的、会拒绝超买单的 fake broker 复现真实券商行为，锁死 order_gen 的卖单优先 + 买力约束修复
（无需依赖 ptp）。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from atrading.config.settings import Settings
from atrading.core.signal_schema import SignalSchemaV1
from atrading.core.strategy_config import StrategyConfig
from atrading.core.types import Bar, Fill, Order, PortfolioState
from atrading.data import InMemoryDataSource
from atrading.decision import PassthroughSizer, RulesDecisionPolicy
from atrading.execution import FileStateStore, TradingLoop
from atrading.risk import PreTradeRiskGate, RiskLimits
from atrading.signals import LLMSignalSource

_T0 = datetime(2026, 1, 1, tzinfo=UTC)


class BuyingPowerBroker:
    """即时成交 + **买力校验**：买单名义超过当前现金即拒绝（不成交），模拟真实券商。"""

    def __init__(self, prices: dict[str, float], *, starting_cash: float) -> None:
        self._prices = prices
        self._cash = starting_cash
        self._positions: dict[str, float] = {}
        self._fills: list[Fill] = []
        self._seen: set[str] = set()
        self.rejected = 0

    def submit(self, order: Order) -> None:
        if order.client_order_id in self._seen:
            return
        price = self._prices.get(order.symbol)
        if price is None or price <= 0:
            return
        notional = order.qty * price
        if order.side == "buy" and notional > self._cash + 1e-9:
            self.rejected += 1  # 买力不足 → 真实券商会拒单
            return
        self._seen.add(order.client_order_id)
        signed = order.qty if order.side == "buy" else -order.qty
        self._positions[order.symbol] = self._positions.get(order.symbol, 0.0) + signed
        self._cash -= signed * price
        self._fills.append(
            Fill(
                client_order_id=order.client_order_id,
                symbol=order.symbol,
                qty=order.qty,
                price=price,
                ts=datetime.now(tz=UTC),
            )
        )

    def advance(self, now: datetime) -> list[Fill]:
        return []

    def get_positions(self) -> PortfolioState:
        invested = sum(s * self._prices.get(sym, 0.0) for sym, s in self._positions.items())
        return PortfolioState(
            ts=datetime.now(tz=UTC),
            cash=self._cash,
            positions=dict(self._positions),
            equity=self._cash + invested,
        )

    def get_open_orders(self) -> list[Order]:
        return []

    def get_fills(self, since: datetime) -> list[Fill]:
        return [f for f in self._fills if f.ts >= since]


def _bars() -> list[Bar]:
    # AAA 上行、BBB 下行 → 每步需卖赢家买输家（再平衡压力测试）。
    out: list[Bar] = []
    for i in range(6):
        ts = _T0 + timedelta(days=i)
        a = 100.0 + 10 * i
        b = 100.0 - 8 * i
        out.append(Bar(symbol="AAA", ts=ts, open=a, high=a, low=a, close=a, volume=1e9))
        out.append(Bar(symbol="BBB", ts=ts, open=b, high=b, low=b, close=b, volume=1e9))
    return out


def _signal(symbol: str) -> SignalSchemaV1:
    return SignalSchemaV1(
        symbol=symbol,
        as_of=_T0,
        sentiment=0.8,
        horizon_days=5,
        confidence=0.9,
        model_version="offline-keyword-v1",
        prompt_version="v1",
        rationale="t",
    )


def test_full_investment_rebalance_no_buying_power_rejects(tmp_path: Path) -> None:
    config = StrategyConfig(
        name="bp",
        universe=["AAA", "BBB"],
        decision_freq="daily",
        max_weight_per_name=1.0,
        max_gross_exposure=1.0,
    )
    prices: dict[str, float] = {}
    broker = BuyingPowerBroker(prices, starting_cash=100_000.0)
    limits = RiskLimits(
        max_position_per_name=1e12,
        max_gross_exposure=1e12,
        max_notional_per_order=1e12,
        max_orders_per_interval=50,
        daily_loss_limit=0.9,
    )
    loop = TradingLoop(
        policy=RulesDecisionPolicy(config, PassthroughSizer(config)),
        data=InMemoryDataSource(_bars()),
        signals=LLMSignalSource([_signal("AAA"), _signal("BBB")]),
        risk_gate=PreTradeRiskGate(limits, Settings(), prices),
        broker=broker,
        state_store=FileStateStore(tmp_path / "s.json"),
        config=config,
        prices=prices,
    )
    timestamps = sorted({b.ts for b in _bars()})
    reports = loop.run(timestamps)

    assert all(not r.degraded for r in reports)
    assert broker.rejected == 0  # 卖单优先 + 买力约束 → 零买力不足拒单
    positions = broker.get_positions().positions
    assert positions.get("AAA", 0.0) > 0.0
    assert positions.get("BBB", 0.0) > 0.0
