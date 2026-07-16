"""过拟合度量：Deflated Sharpe Ratio 与 Probability of Backtest Overfitting。

多重检验会让"最好看的回测"几乎必然出现，即便没有真实 Edge。DSR 用试验次数
(n_trials) 惩罚 Sharpe；PBO 估计"样本内最优在样本外沦为下半区"的概率。
n_trials 由实验框架(M6)自动累加喂入。参考 Bailey & López de Prado。
"""

from __future__ import annotations

import math
from collections.abc import Sequence

_SQRT_2 = math.sqrt(2.0)


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / _SQRT_2))


def _norm_ppf(p: float) -> float:
    """标准正态分位数（Acklam 近似）。"""
    if not 0.0 < p < 1.0:
        msg = "p 必须在 (0,1)"
        raise ValueError(msg)
    a = [
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    ]
    b = [
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    ]
    c = [
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    ]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00, 3.754408661907416e00]
    p_low = 0.02425
    p_high = 1.0 - p_low
    if p < p_low:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        )
    if p <= p_high:
        q = p - 0.5
        r = q * q
        return (
            (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5])
            * q
            / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
        )
    q = math.sqrt(-2.0 * math.log(1.0 - p))
    return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
        (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
    )


def expected_max_sharpe(n_trials: int) -> float:
    """在 n_trials 次独立试验下，纯运气所期望的最大 Sharpe（标准化，均值0方差1）。"""
    if n_trials <= 1:
        return 0.0
    euler = 0.5772156649015329
    e = math.e
    return (1.0 - euler) * _norm_ppf(1.0 - 1.0 / n_trials) + euler * _norm_ppf(
        1.0 - 1.0 / (n_trials * e)
    )


def deflated_sharpe_ratio(
    observed_sharpe: float,
    n_trials: int,
    n_obs: int,
    *,
    skew: float = 0.0,
    kurtosis: float = 3.0,
) -> float:
    """DSR：把观测 Sharpe 相对"多重检验下的期望最大 Sharpe"做显著性检验，返回概率[0,1]。

    observed_sharpe 与 n_obs 为**每期(非年化)**口径。做法：先把观测 Sharpe 标准化
    （考虑偏度/峰度对估计方差的影响，随 n_obs 增长更显著），再减去 n_trials 下纯运气
    的期望最大标准化 Sharpe。返回值越接近 1 越可信；<0.95 视为不显著。
    """
    if n_obs < 2:
        return 0.0
    var_term = 1.0 - skew * observed_sharpe + (kurtosis - 1.0) / 4.0 * observed_sharpe**2
    if var_term <= 0:
        return 0.0
    standardized = observed_sharpe * math.sqrt((n_obs - 1) / var_term)
    expected_max = expected_max_sharpe(n_trials)
    return _norm_cdf(standardized - expected_max)


def pbo(in_sample_ranks: Sequence[float], out_sample_ranks: Sequence[float]) -> float:
    """Probability of Backtest Overfitting 的简化估计。

    对每次试验，给定其样本内排名与样本外排名（0=最好…1=最差的归一化分位）。
    PBO ≈ 样本内最优者在样本外落入下半区(分位>0.5)的频率。这里对"样本内最优"
    做逐点判定的近似：统计样本内分位靠前(<0.5)却样本外靠后(>0.5)的比例。
    """
    if len(in_sample_ranks) != len(out_sample_ranks):
        msg = "in/out sample ranks 长度必须一致"
        raise ValueError(msg)
    n = len(in_sample_ranks)
    if n == 0:
        return 0.0
    flips = sum(
        1
        for is_r, oos_r in zip(in_sample_ranks, out_sample_ranks, strict=True)
        if is_r < 0.5 <= oos_r
    )
    top_half = sum(1 for is_r in in_sample_ranks if is_r < 0.5)
    if top_half == 0:
        return 0.0
    return flips / top_half
