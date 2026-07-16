"""基础绩效指标（纯函数）。

这些是 EVAL 体系的第一层砖：从权益曲线算收益/回撤/夏普。防过拟合的高阶指标
（DSR/PBO、样本外切分）留待 EVAL 里程碑扩展。无 IO、确定性、易 golden 测试。
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def returns_from_equity(equity: Sequence[float]) -> list[float]:
    """由权益曲线计算逐期简单收益率。"""
    out: list[float] = []
    for prev, cur in zip(equity[:-1], equity[1:], strict=False):
        if prev == 0:
            out.append(0.0)
        else:
            out.append(cur / prev - 1.0)
    return out


def total_return(equity: Sequence[float]) -> float:
    if len(equity) < 2 or equity[0] == 0:
        return 0.0
    return equity[-1] / equity[0] - 1.0


def max_drawdown(equity: Sequence[float]) -> float:
    """最大回撤（返回非负值：0.2 表示 -20%）。"""
    peak = -math.inf
    worst = 0.0
    for value in equity:
        peak = max(peak, value)
        if peak > 0:
            drawdown = 1.0 - value / peak
            worst = max(worst, drawdown)
    return worst


def sharpe(returns: Sequence[float], periods_per_year: int = 252, risk_free: float = 0.0) -> float:
    """年化夏普比率。收益样本不足或零波动时返回 0.0。"""
    n = len(returns)
    if n < 2:
        return 0.0
    per_period_rf = risk_free / periods_per_year
    excess = [r - per_period_rf for r in returns]
    mean = sum(excess) / n
    variance = sum((r - mean) ** 2 for r in excess) / (n - 1)
    std = math.sqrt(variance)
    if std == 0:
        return 0.0
    return (mean / std) * math.sqrt(periods_per_year)
