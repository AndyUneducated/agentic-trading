from __future__ import annotations

import pytest

from atrading.core.errors import ConfigError
from atrading.core.strategy_config import StrategyConfig
from atrading.registry import available_policies, build_policy, register_policy


def _cfg() -> StrategyConfig:
    return StrategyConfig(name="t", universe=["AAA", "BBB"], decision_freq="daily")


def test_build_known_policies() -> None:
    for name in ("equal_weight", "momentum", "buy_hold", "rules"):
        assert build_policy(name, _cfg()) is not None


def test_unknown_policy_raises_config_error() -> None:
    with pytest.raises(ConfigError):
        build_policy("does_not_exist", _cfg())


def test_register_custom_policy() -> None:
    register_policy("custom_eq", lambda c: build_policy("equal_weight", c))
    assert "custom_eq" in available_policies()
    assert build_policy("custom_eq", _cfg()) is not None
