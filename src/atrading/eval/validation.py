"""验证切分：把"防过拟合"做成不可绕过的 API。

策略评测必须走这些切分（walk-forward / purged CV），而非在全样本上调参。最终留出集
由 HoldoutGuard 保护——一旦以调参目的访问即留痕，禁止反复"偷看后再调"。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import AwareDatetime, BaseModel


class DateRange(BaseModel):
    start: AwareDatetime
    end: AwareDatetime


class Split(BaseModel):
    train: DateRange
    test: DateRange


def walk_forward(
    start: datetime,
    end: datetime,
    train_span: timedelta,
    test_span: timedelta,
    step: timedelta,
) -> list[Split]:
    """滚动前向验证：训练窗后紧跟测试窗，按 step 滚动。测试窗恒在训练窗之后（无未来）。"""
    if train_span <= timedelta(0) or test_span <= timedelta(0) or step <= timedelta(0):
        msg = "train_span/test_span/step 必须为正"
        raise ValueError(msg)
    splits: list[Split] = []
    train_start = start
    while True:
        train_end = train_start + train_span
        test_start = train_end
        test_end = test_start + test_span
        if test_end > end:
            break
        splits.append(
            Split(
                train=DateRange(start=train_start, end=train_end),
                test=DateRange(start=test_start, end=test_end),
            )
        )
        train_start = train_start + step
    return splits


def purged_kfold(times: list[datetime], k: int, embargo: float = 0.0) -> list[Split]:
    """时间序列 K 折 CV，训练集剔除与测试集重叠的信息 + embargo 缓冲，防泄漏。

    times 需已排序。每折取一段连续时间为测试集；训练集为其余时间，但会 purge 掉
    测试集前后 embargo 比例的样本（避免相邻样本的信息泄漏到训练集）。
    """
    if k < 2:
        msg = "k 必须 >= 2"
        raise ValueError(msg)
    if not 0.0 <= embargo < 1.0:
        msg = "embargo 必须在 [0,1)"
        raise ValueError(msg)
    n = len(times)
    if n < k:
        msg = "样本数必须 >= k"
        raise ValueError(msg)

    fold_size = n // k
    embargo_len = int(n * embargo)
    splits: list[Split] = []
    for fold in range(k):
        test_lo = fold * fold_size
        test_hi = n - 1 if fold == k - 1 else (fold + 1) * fold_size - 1

        train_end_idx = test_lo - 1 - embargo_len
        train_start_after = test_hi + 1 + embargo_len

        # 训练集取测试折之前的部分（purge + embargo 之后）；若没有则取之后的部分。
        if train_end_idx >= 0:
            train = DateRange(start=times[0], end=times[train_end_idx])
        elif train_start_after <= n - 1:
            train = DateRange(start=times[train_start_after], end=times[n - 1])
        else:
            continue
        splits.append(
            Split(
                train=train,
                test=DateRange(start=times[test_lo], end=times[test_hi]),
            )
        )
    return splits


class HoldoutAccess(BaseModel):
    purpose: Literal["final_eval"]
    at: AwareDatetime
    note: str = ""


class HoldoutGuard:
    """最终验证集守卫：访问留痕；默认只允许一次以 final_eval 目的访问。

    结论阶段用它一次性判定，防"偷看后调参"。再次访问会抛错（除非显式 allow_reaccess）。
    """

    def __init__(self, holdout: DateRange, *, allow_reaccess: bool = False) -> None:
        self._holdout = holdout
        self._allow_reaccess = allow_reaccess
        self._accesses: list[HoldoutAccess] = []

    @property
    def accesses(self) -> list[HoldoutAccess]:
        return list(self._accesses)

    @property
    def used(self) -> bool:
        return len(self._accesses) > 0

    def acquire(self, purpose: Literal["final_eval"], *, note: str = "") -> DateRange:
        if self.used and not self._allow_reaccess:
            msg = (
                "最终留出集已被访问过；禁止以调参目的反复访问（防止偷看后过拟合）。"
                f" 既往访问: {len(self._accesses)} 次"
            )
            raise RuntimeError(msg)
        self._accesses.append(HoldoutAccess(purpose=purpose, at=datetime.now(tz=UTC), note=note))
        return self._holdout


__all__ = [
    "DateRange",
    "HoldoutAccess",
    "HoldoutGuard",
    "Split",
    "purged_kfold",
    "walk_forward",
]
