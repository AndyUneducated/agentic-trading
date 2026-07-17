"""上线闸门（M10）：把 go-live 决策收敛为**代码强制的安全红线**。

允许投入真实资金，当且仅当三者同时满足：
1. `GoLiveScorecard.go` 全绿（四层 eval 硬门槛，见 `eval/scorecard.py`）；
2. **人类明确批准**（`human_approved`）——绝不自动上线；
3. `KILL_SWITCH` 未激活。

任一不满足即拒绝，并给出可读的 blockers。对齐 `.cursor/rules/10-trading-safety.mdc`。
"""

from __future__ import annotations

from pydantic import BaseModel

from atrading.eval.scorecard import GoLiveScorecard


class GoLiveGate(BaseModel):
    scorecard: GoLiveScorecard
    human_approved: bool = False  # 默认 False：缺省即不允许（安全默认）
    kill_switch_active: bool = False

    @property
    def allowed(self) -> bool:
        return self.scorecard.go and self.human_approved and not self.kill_switch_active

    def blockers(self) -> list[str]:
        reasons: list[str] = []
        if not self.scorecard.go:
            reasons.append("记分卡未全绿（edge/OOS/DSR/PBO/净成本/drift/护栏 有未通过项）")
        if not self.human_approved:
            reasons.append("缺少人类明确批准（红线：绝不自动上线）")
        if self.kill_switch_active:
            reasons.append("KILL_SWITCH 处于激活状态")
        return reasons
