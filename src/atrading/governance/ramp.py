"""资金放量 / 回滚状态机（M10）。

上线不是"开/关"，而是**逐级放量**：paper → pilot(最小实盘) → ramp → scaled，每级需
观察期 + 记分卡通过才晋级；实测回撤/drift 超阈则**自动降级或停机**（安全优先，不可逆
亏损红线）。halted 需人工复位（`reset`）。确定性纯逻辑，便于测试与审计。
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class LiveStage(StrEnum):
    paper = "paper"  # 模拟盘（无真钱）
    pilot = "pilot"  # 最小额实盘
    ramp = "ramp"  # 逐步放量
    scaled = "scaled"  # 目标规模
    halted = "halted"  # 停机待查（人工复位）


_LADDER: tuple[LiveStage, ...] = (
    LiveStage.paper,
    LiveStage.pilot,
    LiveStage.ramp,
    LiveStage.scaled,
)


class RampConfig(BaseModel):
    min_days_per_stage: int = Field(default=5, ge=0)
    soft_rollback_drawdown: float = Field(default=0.10, gt=0)  # 降一级
    hard_halt_drawdown: float = Field(default=0.20, gt=0)  # 直接停机


class RampDecision(BaseModel):
    action: Literal["promote", "hold", "rollback", "halt"]
    from_stage: LiveStage
    to_stage: LiveStage
    reason: str


class CapitalRampController:
    def __init__(
        self, *, config: RampConfig | None = None, stage: LiveStage = LiveStage.paper
    ) -> None:
        self._config = config or RampConfig()
        self._stage = stage

    @property
    def stage(self) -> LiveStage:
        return self._stage

    def reset(self, stage: LiveStage = LiveStage.paper) -> None:
        """人工复位（停机排查后重新起步）。"""
        self._stage = stage

    def _next_stage(self) -> LiveStage:
        if self._stage not in _LADDER:
            return self._stage
        idx = _LADDER.index(self._stage)
        return _LADDER[min(idx + 1, len(_LADDER) - 1)]

    def _previous_stage(self) -> LiveStage:
        if self._stage not in _LADDER:
            return self._stage
        idx = _LADDER.index(self._stage)
        return _LADDER[idx - 1] if idx > 0 else LiveStage.halted  # paper 再降 → 停机待查

    def evaluate(
        self,
        *,
        scorecard_go: bool,
        live_drawdown: float,
        drift_ok: bool,
        days_at_stage: int,
    ) -> RampDecision:
        cfg = self._config
        if self._stage == LiveStage.halted:
            return self._decide("hold", LiveStage.halted, "已停机，待人工复位")

        # 1) 硬止损：直接停机（安全优先于收益）
        if live_drawdown >= cfg.hard_halt_drawdown:
            return self._decide("halt", LiveStage.halted, "回撤触及硬止损，全面停机待查")

        # 2) 软回滚：回撤超软阈值或 drift 超界（疑似代码分叉/成本低估）→ 降一级
        if live_drawdown >= cfg.soft_rollback_drawdown or not drift_ok:
            reason = (
                "回撤超软阈值，降级观察"
                if live_drawdown >= cfg.soft_rollback_drawdown
                else "drift 超界（疑似回测-实盘分叉/成本低估），降级排查"
            )
            return self._decide("rollback", self._previous_stage(), reason)

        # 3) 晋级：记分卡通过 + 观察期达标 + 未到顶
        if scorecard_go and days_at_stage >= cfg.min_days_per_stage:
            nxt = self._next_stage()
            if nxt != self._stage:
                return self._decide("promote", nxt, "记分卡通过 + 观察期达标，逐级放量")

        return self._decide("hold", self._stage, "维持当前档位")

    def _decide(
        self,
        action: Literal["promote", "hold", "rollback", "halt"],
        to_stage: LiveStage,
        reason: str,
    ) -> RampDecision:
        from_stage = self._stage
        self._stage = to_stage
        return RampDecision(action=action, from_stage=from_stage, to_stage=to_stage, reason=reason)
