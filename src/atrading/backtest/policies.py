"""参考决策策略（实现统一 DecisionPolicy 接口）。

这些既是测试/基准，也示范"决策=纯函数"：仅依赖 DecisionContext，无 IO、不看未来。
回测与实盘调用同一实现（ADR-0003）。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from atrading.core.interfaces import DecisionContext
from atrading.core.types import TargetWeights


class ConstantWeightPolicy:
    """固定目标权重（用于测试与简单基准）。"""

    def __init__(self, weights: Mapping[str, float]) -> None:
        self._weights = dict(weights)

    def decide(self, ctx: DecisionContext) -> TargetWeights:
        return TargetWeights(as_of=ctx.as_of, weights=dict(self._weights))


class SingleAssetBuyHoldPolicy:
    """单标的满仓买入持有（SPY / BTC 基准的精确实现：权重恒为 1，无换手）。"""

    def __init__(self, symbol: str) -> None:
        self._symbol = symbol

    def decide(self, ctx: DecisionContext) -> TargetWeights:
        return TargetWeights(as_of=ctx.as_of, weights={self._symbol: 1.0})


class EqualWeightPolicy:
    """等权（每期再平衡到等权）。"""

    def __init__(self, universe: Sequence[str]) -> None:
        self._universe = list(universe)

    def decide(self, ctx: DecisionContext) -> TargetWeights:
        if not self._universe:
            return TargetWeights(as_of=ctx.as_of, weights={})
        w = 1.0 / len(self._universe)
        return TargetWeights(as_of=ctx.as_of, weights={s: w for s in self._universe})


class PriceOnlyMomentumPolicy:
    """纯价量动量基线：做多 lookback 期为正动量的标的，等权并受单标的上限约束。

    这是 Edge 证伪的关键对照——LLM 信号必须优于这种"只用价格"的策略。
    """

    def __init__(
        self, universe: Sequence[str], lookback: int = 20, max_weight: float = 0.2
    ) -> None:
        self._universe = list(universe)
        self._lookback = lookback
        self._max_weight = max_weight

    def decide(self, ctx: DecisionContext) -> TargetWeights:
        winners: list[str] = []
        for symbol in self._universe:
            bars = ctx.bars.get(symbol, [])
            if len(bars) > self._lookback:
                past = bars[-1 - self._lookback].close
                if past > 0 and (bars[-1].close / past - 1.0) > 0:
                    winners.append(symbol)
        if not winners:
            return TargetWeights(as_of=ctx.as_of, weights={})
        w = min(self._max_weight, 1.0 / len(winners))
        return TargetWeights(as_of=ctx.as_of, weights={s: w for s in winners})
