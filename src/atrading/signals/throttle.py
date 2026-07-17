"""优先级节流（M7）：低频 + 事件驱动 + 预算约束下选择最该分析的标的。

每 tick 对全 universe 调 LLM 经济上不可行。按异常分（|情绪冲击|、成交量激增、
临近事件等，越大越紧急）排序，在下单数/预算上限内择优；被跳过者标注 "AI paused"，
避免产出过期上下文或烧超预算。纯函数、确定性（同分按 symbol 稳定排序）。
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, Field


class SignalRequest(BaseModel):
    symbol: str
    priority: float  # 异常分，越大越紧急
    est_cost_usd: float = Field(default=0.0, ge=0)


class ThrottleResult(BaseModel):
    selected: list[SignalRequest] = Field(default_factory=list)
    paused: list[SignalRequest] = Field(default_factory=list)  # 被跳过（AI paused）


class PriorityThrottler:
    def __init__(self, *, max_requests: int, budget_left_usd: float | None = None) -> None:
        if max_requests < 0:
            msg = "max_requests 不能为负"
            raise ValueError(msg)
        self._max_requests = max_requests
        self._budget_left = budget_left_usd

    def select(self, candidates: Sequence[SignalRequest]) -> ThrottleResult:
        # 优先级降序；同分按 symbol 升序确保确定性。
        ordered = sorted(candidates, key=lambda r: (-r.priority, r.symbol))
        selected: list[SignalRequest] = []
        paused: list[SignalRequest] = []
        spent = 0.0
        for req in ordered:
            over_count = len(selected) >= self._max_requests
            over_budget = (
                self._budget_left is not None and spent + req.est_cost_usd > self._budget_left
            )
            if over_count or over_budget:
                paused.append(req)
                continue
            selected.append(req)
            spent += req.est_cost_usd
        return ThrottleResult(selected=selected, paused=paused)
