"""策略注册表：把配置里的字符串名映射到实现工厂，支持 config 驱动装配。

新增一个决策策略 = 注册一个 builder，无需改动调用方（组合根 / CLI / 实验）。
"""

from __future__ import annotations

from collections.abc import Callable

from atrading.backtest import (
    EqualWeightPolicy,
    PriceOnlyMomentumPolicy,
    SingleAssetBuyHoldPolicy,
)
from atrading.core.errors import ConfigError
from atrading.core.interfaces import DecisionPolicy
from atrading.core.strategy_config import StrategyConfig
from atrading.decision import PassthroughSizer, RulesDecisionPolicy

PolicyBuilder = Callable[[StrategyConfig], DecisionPolicy]


def _equal_weight(config: StrategyConfig) -> DecisionPolicy:
    return EqualWeightPolicy(config.universe)


def _momentum(config: StrategyConfig) -> DecisionPolicy:
    return PriceOnlyMomentumPolicy(config.universe)


def _buy_hold(config: StrategyConfig) -> DecisionPolicy:
    return SingleAssetBuyHoldPolicy(config.universe[0])


def _rules(config: StrategyConfig) -> DecisionPolicy:
    # 混合架构的运行时决策路径：消费 LLM 情绪信号 + 仓位管理约束。
    return RulesDecisionPolicy(config, PassthroughSizer(config))


_POLICY_REGISTRY: dict[str, PolicyBuilder] = {
    "equal_weight": _equal_weight,
    "momentum": _momentum,
    "buy_hold": _buy_hold,
    "rules": _rules,
}


def register_policy(name: str, builder: PolicyBuilder) -> None:
    _POLICY_REGISTRY[name] = builder


def available_policies() -> list[str]:
    return sorted(_POLICY_REGISTRY)


def build_policy(name: str, config: StrategyConfig) -> DecisionPolicy:
    try:
        builder = _POLICY_REGISTRY[name]
    except KeyError as error:
        msg = f"未知策略 {name!r}；可选: {available_policies()}"
        raise ConfigError(msg) from error
    return builder(config)
