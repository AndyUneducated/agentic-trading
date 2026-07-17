"""策略配置契约。

把标的池、决策周期、动作空间、风控上限、基准、评测指标写成类型化配置，
单一数据源，供回测/执行/评测共用。数值阈值（成功指标）在 EVAL 侧引用 CHARTER。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator

from atrading.core.errors import ConfigError


def _default_benchmarks() -> list[str]:
    return ["SPY", "BTC-USD", "price_only"]


def _default_metrics() -> list[str]:
    return ["excess_return", "max_drawdown", "sharpe", "dsr"]


class StrategyConfig(BaseModel):
    name: str
    universe: list[str] = Field(min_length=1)
    decision_freq: Literal["intraday", "daily", "weekly"]
    allow_short: bool = False
    max_gross_exposure: float = Field(default=1.0, gt=0)
    max_weight_per_name: float = Field(default=0.2, gt=0, le=1)
    # 信号时效：超过该天数的旧信号视为过期、不参与决策；None=不设时效（默认）。
    max_signal_age_days: int | None = Field(default=None, gt=0)
    benchmarks: list[str] = Field(default_factory=_default_benchmarks)
    primary_metrics: list[str] = Field(default_factory=_default_metrics)

    @model_validator(mode="after")
    def _check_consistency(self) -> StrategyConfig:
        if len(set(self.universe)) != len(self.universe):
            msg = "universe 含重复标的"
            raise ValueError(msg)
        if self.max_weight_per_name > self.max_gross_exposure:
            msg = "max_weight_per_name 不应超过 max_gross_exposure"
            raise ValueError(msg)
        return self

    @classmethod
    def from_yaml(cls, path: str | Path) -> StrategyConfig:
        try:
            data: Any = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as error:
            msg = f"读取策略配置失败: {path}: {error}"
            raise ConfigError(msg) from error
        try:
            return cls.model_validate(data)
        except Exception as error:  # noqa: BLE001 — 统一转换为 ConfigError
            msg = f"策略配置非法: {path}: {error}"
            raise ConfigError(msg) from error
