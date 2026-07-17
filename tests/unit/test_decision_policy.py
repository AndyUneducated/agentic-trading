"""RulesDecisionPolicy 单元测试：按 as_of 取最新信号（不依赖列表顺序）。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from atrading.core.interfaces import DecisionContext
from atrading.core.strategy_config import StrategyConfig
from atrading.core.types import PortfolioState, Signal
from atrading.decision import PassthroughSizer, RulesDecisionPolicy

_D1 = datetime(2026, 1, 1, tzinfo=UTC)
_D2 = datetime(2026, 1, 2, tzinfo=UTC)


def _sentiment(symbol: str, as_of: datetime, value: float) -> Signal:
    return Signal(symbol=symbol, as_of=as_of, name="sentiment", value=value, confidence=0.9)


def _ctx(signals: list[Signal]) -> DecisionContext:
    return DecisionContext(
        as_of=_D2,
        bars={"AAA": []},
        signals=signals,
        portfolio=PortfolioState(ts=_D2, cash=100_000.0, positions={}, equity=100_000.0),
    )


def _policy() -> RulesDecisionPolicy:
    config = StrategyConfig(name="t", universe=["AAA"], decision_freq="daily")
    return RulesDecisionPolicy(config, PassthroughSizer(config))


def test_picks_most_recent_signal_regardless_of_list_order() -> None:
    # 列表顺序把"较旧的正面信号"放最后；正确实现应采用**较新**的负面信号 → 不建仓。
    signals = [_sentiment("AAA", _D2, -0.9), _sentiment("AAA", _D1, 0.9)]
    weights = _policy().decide(_ctx(signals)).weights
    assert weights == {}


def test_acts_on_recent_positive_signal() -> None:
    # 较新为正面（旧的负面放最后）→ 应建仓。
    signals = [_sentiment("AAA", _D2, 0.9), _sentiment("AAA", _D1, -0.9)]
    weights = _policy().decide(_ctx(signals)).weights
    assert weights.get("AAA", 0.0) > 0.0


def _policy_with_staleness(max_age_days: int) -> RulesDecisionPolicy:
    config = StrategyConfig(
        name="t", universe=["AAA"], decision_freq="daily", max_signal_age_days=max_age_days
    )
    return RulesDecisionPolicy(config, PassthroughSizer(config))


def test_stale_signal_is_ignored() -> None:
    # as_of=_D2；信号来自 10 天前，max_signal_age_days=3 → 过期，不建仓。
    old = _sentiment("AAA", _D2 - timedelta(days=10), 0.9)
    weights = _policy_with_staleness(3).decide(_ctx([old])).weights
    assert weights == {}


def test_fresh_signal_within_window_is_used() -> None:
    fresh = _sentiment("AAA", _D2 - timedelta(days=1), 0.9)
    weights = _policy_with_staleness(3).decide(_ctx([fresh])).weights
    assert weights.get("AAA", 0.0) > 0.0
