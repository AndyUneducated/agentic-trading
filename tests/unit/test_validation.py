from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atrading.eval import HoldoutGuard, purged_kfold, walk_forward
from atrading.eval.validation import DateRange


def test_walk_forward_ordering_and_bounds() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 3, 1, tzinfo=UTC)
    splits = walk_forward(
        start,
        end,
        train_span=timedelta(days=20),
        test_span=timedelta(days=10),
        step=timedelta(days=10),
    )
    assert len(splits) > 0
    for split in splits:
        assert split.test.start == split.train.end  # 测试紧跟训练
        assert split.test.start >= split.train.start
        assert split.test.end <= end  # 不越界


def test_walk_forward_rejects_nonpositive() -> None:
    with pytest.raises(ValueError, match="必须为正"):
        walk_forward(
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 2, 1, tzinfo=UTC),
            train_span=timedelta(0),
            test_span=timedelta(days=1),
            step=timedelta(days=1),
        )


def test_purged_kfold_produces_k_folds() -> None:
    times = [datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=i) for i in range(50)]
    splits = purged_kfold(times, k=5, embargo=0.02)
    assert len(splits) == 5
    for split in splits:
        assert split.test.start <= split.test.end


def test_holdout_guard_blocks_reaccess() -> None:
    holdout = DateRange(
        start=datetime(2026, 6, 1, tzinfo=UTC), end=datetime(2026, 12, 31, tzinfo=UTC)
    )
    guard = HoldoutGuard(holdout)
    first = guard.acquire("final_eval", note="final judgement")
    assert first.start == holdout.start
    assert guard.used
    with pytest.raises(RuntimeError, match="禁止.*反复访问"):
        guard.acquire("final_eval")
    assert len(guard.accesses) == 1


def test_holdout_guard_allows_reaccess_when_configured() -> None:
    holdout = DateRange(
        start=datetime(2026, 6, 1, tzinfo=UTC), end=datetime(2026, 12, 31, tzinfo=UTC)
    )
    guard = HoldoutGuard(holdout, allow_reaccess=True)
    guard.acquire("final_eval")
    guard.acquire("final_eval")
    assert len(guard.accesses) == 2
