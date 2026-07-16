"""执行对账：内部状态 vs 券商真实状态。

检测漏单/重复成交/持仓漂移。启动时 + 周期性对账；不一致超阈 → 告警（可选熔断）。
用 client_order_id 匹配成交（借鉴 Nautilus LiveExecutionEngine 思路）。
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from atrading.core.interfaces import Broker
from atrading.execution.state_store import EngineState


class ReconcileReport(BaseModel):
    unexpected_fills: list[str] = Field(default_factory=list)  # 券商有、我们没记录的成交
    position_mismatches: dict[str, tuple[float, float]] = Field(default_factory=dict)
    # symbol -> (internal_shares, broker_shares)

    @property
    def ok(self) -> bool:
        return not self.unexpected_fills and not self.position_mismatches


class Reconciler:
    def __init__(self, *, position_tol: float = 1e-6) -> None:
        self._position_tol = position_tol

    def reconcile(self, broker: Broker, state: EngineState) -> ReconcileReport:
        broker_state = broker.get_positions()

        # 1) 持仓对齐
        mismatches: dict[str, tuple[float, float]] = {}
        symbols = set(state.positions) | set(broker_state.positions)
        for symbol in symbols:
            internal = state.positions.get(symbol, 0.0)
            actual = broker_state.positions.get(symbol, 0.0)
            if abs(internal - actual) > self._position_tol:
                mismatches[symbol] = (internal, actual)

        # 2) 成交对齐：券商有、但我们从未提交过该 client_order_id
        submitted = set(state.submitted_order_ids)
        fills = broker.get_fills(datetime(1970, 1, 1, tzinfo=UTC))
        unexpected = sorted(
            {fill.client_order_id for fill in fills if fill.client_order_id not in submitted}
        )

        return ReconcileReport(unexpected_fills=unexpected, position_mismatches=mismatches)
