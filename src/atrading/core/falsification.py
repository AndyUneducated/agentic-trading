"""Edge 证伪判定（供 EVAL/M4/M6 复用）。

对齐 PROJECT_CHARTER 的证伪口径：信号/策略必须同时优于多类基线且达显著性，
否则 Edge 假设不成立。`beats_oss_baseline` 为 M6 的额外现实性校验，不计入
`edge_confirmed`（后者是进入模拟盘闭环前的最低门槛）。
"""

from __future__ import annotations

from pydantic import BaseModel


class EdgeCriteria(BaseModel):
    beats_zero_baseline: bool = False
    beats_price_only: bool = False
    beats_buy_hold: bool = False
    beats_oss_baseline: bool = False
    significance_ok: bool = False

    @property
    def edge_confirmed(self) -> bool:
        return all(
            [
                self.beats_zero_baseline,
                self.beats_price_only,
                self.beats_buy_hold,
                self.significance_ok,
            ]
        )
