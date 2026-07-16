from pathlib import Path

import pytest
from pydantic import ValidationError

from atrading.core.strategy_config import StrategyConfig

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MVP = _REPO_ROOT / "configs" / "strategies" / "mvp.yaml"


def test_load_mvp_yaml() -> None:
    config = StrategyConfig.from_yaml(_MVP)
    assert config.name == "mvp_hybrid"
    assert config.decision_freq == "daily"
    assert config.allow_short is False
    assert "SPY" in config.universe
    assert "BTC-USD" in config.universe
    assert "price_only" in config.benchmarks


def test_duplicate_universe_rejected() -> None:
    with pytest.raises(ValidationError):
        StrategyConfig(name="dup", universe=["AAPL", "AAPL"], decision_freq="daily")


def test_weight_exceeding_gross_rejected() -> None:
    with pytest.raises(ValidationError):
        StrategyConfig(
            name="bad",
            universe=["AAPL"],
            decision_freq="daily",
            max_gross_exposure=0.5,
            max_weight_per_name=0.8,
        )


def test_empty_universe_rejected() -> None:
    with pytest.raises(ValidationError):
        StrategyConfig(name="empty", universe=[], decision_freq="daily")
