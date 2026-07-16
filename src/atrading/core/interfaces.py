"""核心接口契约（Protocol）。

先把这些接口定稳，各模块据此并行实现并可 mock 依赖。回测与实盘共用同一
`DecisionPolicy`（ADR-0003：回测-实盘一致）。环境差异（数据来源、下单通道、时钟）
全部隔离在 `DataSource` / `Broker` / `Clock` 的不同实现里。
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Protocol

from pydantic import AwareDatetime, BaseModel

from atrading.core.types import (
    Bar,
    Fill,
    Order,
    PortfolioState,
    Signal,
    TargetWeights,
)


class Clock(Protocol):
    """时间源：回测=模拟时钟，实盘=真实时钟。"""

    def now(self) -> datetime: ...


class DataSource(Protocol):
    """行情数据源。约束：只返回 as_of<=now 的数据（PIT，无未来函数）。"""

    def get_bars(
        self, symbols: list[str], start: datetime, end: datetime, freq: str
    ) -> Iterable[Bar]: ...


class SignalSource(Protocol):
    """信号源：返回截至 `ts` 可用的信号。"""

    def signals_as_of(self, ts: datetime, symbols: list[str]) -> list[Signal]: ...


class DecisionContext(BaseModel):
    """决策输入快照：截至 `as_of` 的历史、信号与组合状态。"""

    as_of: AwareDatetime
    bars: dict[str, list[Bar]]
    signals: list[Signal]
    portfolio: PortfolioState


class DecisionPolicy(Protocol):
    """统一决策接口（ADR-0003）：回测与实盘调用同一实现，且应为纯函数。"""

    def decide(self, ctx: DecisionContext) -> TargetWeights: ...


class RiskDecision(BaseModel):
    """预交易风控结果：放行的订单与被拒的订单（附原因）。"""

    approved: list[Order]
    denied: list[tuple[Order, str]]


class RiskGate(Protocol):
    """预交易风控门：所有订单必过。"""

    def check(self, orders: list[Order], portfolio: PortfolioState) -> RiskDecision: ...


class Broker(Protocol):
    """券商适配（模拟盘/实盘）。"""

    def submit(self, order: Order) -> None: ...
    def get_positions(self) -> PortfolioState: ...
    def get_open_orders(self) -> list[Order]: ...
    def get_fills(self, since: datetime) -> list[Fill]: ...
