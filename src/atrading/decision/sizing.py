"""仓位管理（PositionSizer）。

把"原始意图权重"转成"受约束的目标权重"：应用单标的上限、禁止做空（可配）、
总敞口上限；波动率目标法额外按估计波动缩放敞口，避免高波动期过度暴露。
所有实现为纯函数式，回测/实盘共用（ADR-0003）。
"""

from __future__ import annotations

import math
from typing import Protocol

from atrading.core.interfaces import DecisionContext
from atrading.core.strategy_config import StrategyConfig


def apply_constraints(weights: dict[str, float], config: StrategyConfig) -> dict[str, float]:
    """裁剪到 StrategyConfig 约束：禁空(可配)、单标的上限、总敞口上限。"""
    cleaned: dict[str, float] = {}
    for symbol, weight in weights.items():
        w = weight
        if not config.allow_short and w < 0:
            w = 0.0
        if w > config.max_weight_per_name:
            w = config.max_weight_per_name
        if w < -config.max_weight_per_name:
            w = -config.max_weight_per_name
        if w != 0.0:
            cleaned[symbol] = w

    gross = sum(abs(w) for w in cleaned.values())
    if gross > config.max_gross_exposure and gross > 0:
        scale = config.max_gross_exposure / gross
        cleaned = {s: w * scale for s, w in cleaned.items()}
    return cleaned


class PositionSizer(Protocol):
    def size(self, raw_weights: dict[str, float], ctx: DecisionContext) -> dict[str, float]: ...


class PassthroughSizer:
    """恒等 + 约束裁剪（最简 sizer）。"""

    def __init__(self, config: StrategyConfig) -> None:
        self._config = config

    def size(self, raw_weights: dict[str, float], ctx: DecisionContext) -> dict[str, float]:
        return apply_constraints(raw_weights, self._config)


class VolatilityTargetSizer:
    """波动率目标：按各标的近期波动缩放敞口，使组合估计波动趋近 target_vol。

    组合波动用独立性假设近似 sqrt(Σ w_i^2 σ_i^2)。数据不足时退回原始权重（再裁剪）。
    """

    def __init__(
        self, config: StrategyConfig, *, target_vol: float = 0.01, lookback: int = 20
    ) -> None:
        self._config = config
        self._target_vol = target_vol
        self._lookback = lookback

    def _asset_vol(self, ctx: DecisionContext, symbol: str) -> float | None:
        bars = ctx.bars.get(symbol, [])
        if len(bars) <= self._lookback:
            return None
        window = bars[-(self._lookback + 1) :]
        rets = [
            window[i].close / window[i - 1].close - 1.0
            for i in range(1, len(window))
            if window[i - 1].close > 0
        ]
        if len(rets) < 2:
            return None
        mean = sum(rets) / len(rets)
        variance = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
        return math.sqrt(variance)

    def size(self, raw_weights: dict[str, float], ctx: DecisionContext) -> dict[str, float]:
        constrained = apply_constraints(raw_weights, self._config)
        portfolio_var = 0.0
        have_vol = False
        for symbol, weight in constrained.items():
            sigma = self._asset_vol(ctx, symbol)
            if sigma is not None:
                portfolio_var += (weight * sigma) ** 2
                have_vol = True
        if not have_vol or portfolio_var <= 0:
            return constrained
        portfolio_vol = math.sqrt(portfolio_var)
        scale = self._target_vol / portfolio_vol
        scaled = {s: w * scale for s, w in constrained.items()}
        return apply_constraints(scaled, self._config)
