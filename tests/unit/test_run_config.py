from __future__ import annotations

from pathlib import Path

import pytest

from atrading.config import RunConfig
from atrading.core.errors import ConfigError
from atrading.core.risk_limits import RiskLimits

_RISK_YAML = (
    "max_position_per_name: 25000\n"
    "max_gross_exposure: 100000\n"
    "max_notional_per_order: 20000\n"
    "max_orders_per_interval: 10\n"
    "daily_loss_limit: 0.03\n"
)


def test_load_repo_paper_config() -> None:
    rc = RunConfig.from_yaml("configs/paper.yaml")
    assert rc.risk.max_orders_per_interval == 10
    assert rc.logging.format == "json"
    # strategy 路径应解析为绝对路径并可加载
    assert Path(rc.strategy).is_absolute()
    strat = rc.load_strategy()
    assert strat.universe  # 非空


def test_risk_limits_from_yaml(tmp_path: Path) -> None:
    path = tmp_path / "risk.yaml"
    path.write_text(_RISK_YAML, encoding="utf-8")
    limits = RiskLimits.from_yaml(path)
    assert limits.max_gross_exposure == 100000


def test_missing_file_raises_config_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        RunConfig.from_yaml(tmp_path / "nope.yaml")


def test_missing_required_keys_raises(tmp_path: Path) -> None:
    path = tmp_path / "c.yaml"
    path.write_text("logging:\n  level: INFO\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        RunConfig.from_yaml(path)


def test_invalid_risk_value_raises(tmp_path: Path) -> None:
    path = tmp_path / "c.yaml"
    path.write_text(
        "strategy: s.yaml\n"
        "risk:\n"
        "  max_position_per_name: -1\n"
        "  max_gross_exposure: 100000\n"
        "  max_notional_per_order: 20000\n"
        "  max_orders_per_interval: 10\n"
        "  daily_loss_limit: 0.03\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        RunConfig.from_yaml(path)


def test_strategy_path_resolved_relative_to_config(tmp_path: Path) -> None:
    (tmp_path / "risk.yaml").write_text(_RISK_YAML, encoding="utf-8")
    strat = tmp_path / "strat.yaml"
    strat.write_text("name: t\nuniverse: [AAA, BBB]\ndecision_freq: daily\n", encoding="utf-8")
    cfg = tmp_path / "run.yaml"
    cfg.write_text(
        "strategy: strat.yaml\n"
        "risk:\n"
        "  max_position_per_name: 25000\n"
        "  max_gross_exposure: 100000\n"
        "  max_notional_per_order: 20000\n"
        "  max_orders_per_interval: 10\n"
        "  daily_loss_limit: 0.03\n",
        encoding="utf-8",
    )
    rc = RunConfig.from_yaml(cfg)
    assert Path(rc.strategy) == strat.resolve()
    assert rc.load_strategy().name == "t"
