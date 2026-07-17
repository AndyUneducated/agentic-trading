"""LLM 成本预算与熔断（M7）。

跟踪每日/累计花费；超限即熔断（`can_spend` 返回 False / `check` 抛错），配合 AIGateway
安全降级（停止真实调用而非盲目继续烧钱）。对齐 CHARTER §8 预算约束。时间可注入以便确定性测试。
"""

from __future__ import annotations

from datetime import UTC, date, datetime


class BudgetExceededError(RuntimeError):
    """预算耗尽：调用方应安全降级（缓存/便宜后端/暂停信号），不得继续真实调用。"""


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


class CostBudget:
    def __init__(
        self,
        *,
        daily_limit_usd: float,
        total_limit_usd: float | None = None,
    ) -> None:
        if daily_limit_usd < 0:
            msg = "daily_limit_usd 不能为负"
            raise ValueError(msg)
        self._daily_limit = daily_limit_usd
        self._total_limit = total_limit_usd
        self._by_day: dict[date, float] = {}
        self._total = 0.0

    def spent_today(self, *, now: datetime | None = None) -> float:
        day = (now or _utcnow()).date()
        return self._by_day.get(day, 0.0)

    def spent_total(self) -> float:
        return self._total

    def remaining(self, *, now: datetime | None = None) -> float:
        day_left = self._daily_limit - self.spent_today(now=now)
        if self._total_limit is not None:
            return min(day_left, self._total_limit - self._total)
        return day_left

    def can_spend(self, amount: float = 0.0, *, now: datetime | None = None) -> bool:
        return self.remaining(now=now) >= amount

    def check(self, *, now: datetime | None = None) -> None:
        if self.remaining(now=now) <= 0.0:
            msg = "LLM 预算已耗尽（日/累计上限）"
            raise BudgetExceededError(msg)

    def record(self, amount: float, *, now: datetime | None = None) -> None:
        day = (now or _utcnow()).date()
        self._by_day[day] = self._by_day.get(day, 0.0) + amount
        self._total += amount
