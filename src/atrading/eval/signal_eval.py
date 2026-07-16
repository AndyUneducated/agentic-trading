"""信号级评测（EVAL 第二层，独立于交易盈亏）。

衡量信号对未来收益的预测力：IC（Pearson）、rank-IC（Spearman）、命中率与显著性
（IC 的 t 统计量）。另含保守偏差检查——LLM 已知会系统性偏空/偏低置信。

通过判据（在更上层组合）：显著优于零基线 **且** 优于 price_only 基线，防"复述已定价信息"。
纯 Python、无 IO、可手算校验。
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from pydantic import BaseModel


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    var_x = sum((x - mx) ** 2 for x in xs)
    var_y = sum((y - my) ** 2 for y in ys)
    if var_x == 0 or var_y == 0:
        return 0.0
    return cov / math.sqrt(var_x * var_y)


def _ranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        average_rank = (i + j) / 2.0
        for k in range(i, j + 1):
            ranks[order[k]] = average_rank
        i = j + 1
    return ranks


def _spearman(xs: Sequence[float], ys: Sequence[float]) -> float:
    return _pearson(_ranks(xs), _ranks(ys))


class SignalEvalResult(BaseModel):
    n: int
    ic: float
    rank_ic: float
    hit_rate: float
    ic_t_stat: float

    def is_significant(self, t_threshold: float = 2.0) -> bool:
        return abs(self.ic_t_stat) >= t_threshold


def evaluate_signal(
    signal_values: Sequence[float], forward_returns: Sequence[float]
) -> SignalEvalResult:
    """给定信号值与其后（as_of 之后）的前瞻收益，计算预测力指标。

    调用方须保证 forward_returns 严格取自 signal.as_of 之后（防前视，PIT 对齐）。
    """
    if len(signal_values) != len(forward_returns):
        msg = "signal_values 与 forward_returns 长度必须一致"
        raise ValueError(msg)
    n = len(signal_values)

    ic = _pearson(signal_values, forward_returns)
    rank_ic = _spearman(signal_values, forward_returns)

    comparable = [(s, r) for s, r in zip(signal_values, forward_returns, strict=True) if s != 0]
    if comparable:
        hits = sum(1 for s, r in comparable if (s > 0 and r > 0) or (s < 0 and r < 0))
        hit_rate = hits / len(comparable)
    else:
        hit_rate = 0.0

    ic_t_stat = ic * math.sqrt((n - 2) / (1.0 - ic**2)) if n > 2 and abs(ic) < 1.0 else 0.0

    return SignalEvalResult(n=n, ic=ic, rank_ic=rank_ic, hit_rate=hit_rate, ic_t_stat=ic_t_stat)


class ConservatismReport(BaseModel):
    n: int
    mean_sentiment: float
    frac_negative: float
    biased: bool


def check_conservatism(
    sentiments: Sequence[float],
    *,
    mean_threshold: float = -0.2,
    neg_frac_threshold: float = 0.65,
) -> ConservatismReport:
    """检查信号是否系统性偏空：均值过低或看空占比过高即判定有保守偏差。"""
    n = len(sentiments)
    if n == 0:
        return ConservatismReport(n=0, mean_sentiment=0.0, frac_negative=0.0, biased=False)
    mean_sentiment = sum(sentiments) / n
    frac_negative = sum(1 for s in sentiments if s < 0) / n
    biased = mean_sentiment < mean_threshold or frac_negative > neg_frac_threshold
    return ConservatismReport(
        n=n,
        mean_sentiment=mean_sentiment,
        frac_negative=frac_negative,
        biased=biased,
    )
