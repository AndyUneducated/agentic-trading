from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atrading.signals.budget import BudgetExceededError, CostBudget

_DAY1 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
_DAY2 = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)


def test_records_and_remaining() -> None:
    budget = CostBudget(daily_limit_usd=1.0)
    assert budget.remaining(now=_DAY1) == 1.0
    budget.record(0.4, now=_DAY1)
    assert budget.remaining(now=_DAY1) == pytest.approx(0.6)
    assert budget.can_spend(0.5, now=_DAY1)
    assert not budget.can_spend(0.7, now=_DAY1)


def test_daily_reset_across_days() -> None:
    budget = CostBudget(daily_limit_usd=1.0)
    budget.record(1.0, now=_DAY1)
    assert not budget.can_spend(0.1, now=_DAY1)
    assert budget.can_spend(1.0, now=_DAY2)  # 次日重置


def test_check_raises_when_exhausted() -> None:
    budget = CostBudget(daily_limit_usd=0.5)
    budget.check(now=_DAY1)  # 未耗尽不抛
    budget.record(0.5, now=_DAY1)
    with pytest.raises(BudgetExceededError):
        budget.check(now=_DAY1)


def test_total_limit_caps_across_days() -> None:
    budget = CostBudget(daily_limit_usd=10.0, total_limit_usd=1.2)
    budget.record(1.0, now=_DAY1)
    assert budget.remaining(now=_DAY2) == pytest.approx(0.2)  # 受累计上限约束
    assert not budget.can_spend(0.5, now=_DAY2)
