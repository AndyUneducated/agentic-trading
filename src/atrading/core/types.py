"""领域核心类型（contracts-first）。

这些是全系统的"宪法"：数据、信号、订单、组合状态的类型化契约。
所有带时间的字段用 `AwareDatetime`（必须带时区），杜绝 naive datetime 导致的
时区错误与 look-ahead。回测与实盘共用这些类型。
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field


class OrderStatus(StrEnum):
    """订单生命周期状态。即时成交的模拟 broker 从 new 直达 filled；高保真/真实 broker
    会经过 partially_filled，或以 rejected/canceled 终止。"""

    new = "new"
    partially_filled = "partially_filled"
    filled = "filled"
    rejected = "rejected"
    canceled = "canceled"


class Bar(BaseModel):
    """单标的的一根 OHLCV K 线。`ts` 为 bar 收盘时刻（UTC）。"""

    symbol: str
    ts: AwareDatetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class Signal(BaseModel):
    """通用因子记录：某标的在 `as_of` 时刻的一个命名因子值。

    `as_of` 表示"信号当时可用"的时刻（PIT）；`value` 为因子取值，`name` 为因子名。
    """

    symbol: str
    as_of: AwareDatetime
    name: str
    value: float
    confidence: float = Field(ge=0, le=1, default=1.0)
    model_version: str | None = None
    prompt_version: str | None = None
    rationale: str | None = None


class TargetWeights(BaseModel):
    """决策层输出：目标组合权重（symbol -> 权重）。"""

    as_of: AwareDatetime
    weights: dict[str, float] = Field(default_factory=dict)


class Order(BaseModel):
    """订单。`client_order_id` 为幂等键，用于对账与崩溃恢复防重复下单。"""

    symbol: str
    side: Literal["buy", "sell"]
    qty: float = Field(gt=0)
    order_type: Literal["market", "limit"] = "market"
    limit_price: float | None = None
    client_order_id: str


class Fill(BaseModel):
    """成交回报。"""

    client_order_id: str
    symbol: str
    qty: float
    price: float
    ts: AwareDatetime
    fee: float = 0.0


class PortfolioState(BaseModel):
    """某时刻的组合状态。"""

    ts: AwareDatetime
    cash: float
    positions: dict[str, float] = Field(default_factory=dict)
    equity: float
