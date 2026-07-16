"""Regime / 模型衰减检测与刷新策略。

检测分布漂移（波动率放大/相关性结构变化），对抗非平稳市场；定义刷新/降杠杆/退役的
触发条件。方法选**统计漂移**（波动率比 + 平均相关性偏移）：简单、可解释、无需训练，
适合作为一线告警（更复杂的变点检测后续按需引入，见 ADR-0007）。
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel


class RegimeReport(BaseModel):
    vol_ratio: float  # 近期波动 / 参考波动
    corr_shift: float  # |近期平均相关性 - 参考平均相关性|
    shifted: bool


class RefreshPolicy(BaseModel):
    drift_threshold: float = 0.3
    min_live_days_before_refresh: int = 20
    action_on_shift: Literal["alert", "reduce_exposure", "retire"] = "alert"

    def decide(self, report: RegimeReport, live_days: int) -> str:
        if not report.shifted:
            return "hold"
        if live_days < self.min_live_days_before_refresh:
            return "alert"  # 样本不足，先告警不动作
        return self.action_on_shift


def _std(values: Sequence[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    return math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1))


def _pearson(a: Sequence[float], b: Sequence[float]) -> float:
    n = min(len(a), len(b))
    if n < 2:
        return 0.0
    a2, b2 = a[:n], b[:n]
    ma, mb = sum(a2) / n, sum(b2) / n
    cov = sum((a2[i] - ma) * (b2[i] - mb) for i in range(n))
    va = sum((x - ma) ** 2 for x in a2)
    vb = sum((x - mb) ** 2 for x in b2)
    if va <= 0 or vb <= 0:
        return 0.0
    return cov / math.sqrt(va * vb)


def _mean_vol(returns_by_symbol: dict[str, Sequence[float]]) -> float:
    vols = [_std(rets) for rets in returns_by_symbol.values() if len(rets) >= 2]
    return sum(vols) / len(vols) if vols else 0.0


def _mean_pairwise_corr(returns_by_symbol: dict[str, Sequence[float]]) -> float:
    symbols = sorted(returns_by_symbol)
    corrs: list[float] = []
    for i in range(len(symbols)):
        for j in range(i + 1, len(symbols)):
            corrs.append(_pearson(returns_by_symbol[symbols[i]], returns_by_symbol[symbols[j]]))
    return sum(corrs) / len(corrs) if corrs else 0.0


class RegimeMonitor:
    def __init__(
        self, *, vol_ratio_threshold: float = 1.5, corr_shift_threshold: float = 0.3
    ) -> None:
        self._vol_ratio_threshold = vol_ratio_threshold
        self._corr_shift_threshold = corr_shift_threshold

    def detect_shift(
        self,
        recent: dict[str, Sequence[float]],
        reference: dict[str, Sequence[float]],
    ) -> RegimeReport:
        ref_vol = _mean_vol(reference)
        rec_vol = _mean_vol(recent)
        vol_ratio = rec_vol / ref_vol if ref_vol > 0 else (1.0 if rec_vol == 0 else math.inf)
        corr_shift = abs(_mean_pairwise_corr(recent) - _mean_pairwise_corr(reference))

        shifted = (
            vol_ratio >= self._vol_ratio_threshold
            or (vol_ratio > 0 and vol_ratio <= 1.0 / self._vol_ratio_threshold)
            or corr_shift >= self._corr_shift_threshold
        )
        return RegimeReport(vol_ratio=vol_ratio, corr_shift=corr_shift, shifted=shifted)
