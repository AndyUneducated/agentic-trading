"""规则/量化决策层（实现统一 DecisionPolicy）。

混合架构的"决策"半边：消费 LLM 情绪信号 + 价量，产出目标权重。纯函数、无 IO、
不看未来——回测(M3)与实盘(M5)调用**同一实现**（ADR-0003）。LLM 只提供信号，
下单与否由这里的确定性规则决定（红线：LLM 不下单）。
"""

from __future__ import annotations

from datetime import datetime

from atrading.core.interfaces import DecisionContext
from atrading.core.strategy_config import StrategyConfig
from atrading.core.types import TargetWeights
from atrading.decision.sizing import PositionSizer


class RulesDecisionPolicy:
    """做多情绪显著为正的标的，等权作为原始意图，再交给 sizer 做仓位管理与约束。

    - `sentiment_threshold`：情绪须超过此阈值才建仓（过滤噪声/弱信号）。
    - `min_confidence`：低置信信号忽略。
    - 无合格信号 → 空仓（现金），这是安全默认。
    """

    def __init__(
        self,
        config: StrategyConfig,
        sizer: PositionSizer,
        *,
        sentiment_threshold: float = 0.0,
        min_confidence: float = 0.0,
    ) -> None:
        self._config = config
        self._sizer = sizer
        self._sentiment_threshold = sentiment_threshold
        self._min_confidence = min_confidence

    def decide(self, ctx: DecisionContext) -> TargetWeights:
        universe = set(self._config.universe)
        # symbol -> (as_of, sentiment, confidence)；按 as_of 取最新，不依赖信号列表顺序。
        latest: dict[str, tuple[datetime, float, float]] = {}
        for signal in ctx.signals:
            if signal.name != "sentiment" or signal.symbol not in universe:
                continue
            prior = latest.get(signal.symbol)
            if prior is None or signal.as_of >= prior[0]:
                latest[signal.symbol] = (signal.as_of, signal.value, signal.confidence)

        selected = [
            symbol
            for symbol, (_as_of, sentiment, confidence) in latest.items()
            if sentiment > self._sentiment_threshold and confidence >= self._min_confidence
        ]
        if not selected:
            return TargetWeights(as_of=ctx.as_of, weights={})

        raw_weight = 1.0 / len(selected)
        raw = {symbol: raw_weight for symbol in selected}
        sized = self._sizer.size(raw, ctx)
        return TargetWeights(as_of=ctx.as_of, weights=sized)
