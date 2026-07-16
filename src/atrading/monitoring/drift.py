"""live-vs-backtest drift 监控。

持续对比模拟盘(M5)实测 vs 同期回测(同一 DecisionPolicy)的权重/收益偏离。drift 大 =
要么真实摩擦被低估（改成本模型），要么代码分叉（违反 ADR-0003，须排查）。构造
"实盘=回测"应得 drift≈0。
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel


class DriftReport(BaseModel):
    weight_l1: float  # 各期权重 L1 距离的平均（实盘 vs 回测）
    return_gap: float  # 实盘总收益 - 回测总收益
    within_bounds: bool


def _total_return(equity: Sequence[float]) -> float:
    if len(equity) < 2 or equity[0] == 0:
        return 0.0
    return equity[-1] / equity[0] - 1.0


def compute_drift(
    live_weights: Sequence[dict[str, float]],
    backtest_weights: Sequence[dict[str, float]],
    live_equity: Sequence[float],
    backtest_equity: Sequence[float],
    *,
    weight_tol: float = 0.05,
    return_tol: float = 0.02,
) -> DriftReport:
    n = min(len(live_weights), len(backtest_weights))
    if n == 0:
        weight_l1 = 0.0
    else:
        total = 0.0
        for i in range(n):
            live_w, bt_w = live_weights[i], backtest_weights[i]
            symbols = set(live_w) | set(bt_w)
            total += sum(abs(live_w.get(s, 0.0) - bt_w.get(s, 0.0)) for s in symbols)
        weight_l1 = total / n

    return_gap = _total_return(live_equity) - _total_return(backtest_equity)
    within_bounds = weight_l1 <= weight_tol and abs(return_gap) <= return_tol
    return DriftReport(weight_l1=weight_l1, return_gap=return_gap, within_bounds=within_bounds)
