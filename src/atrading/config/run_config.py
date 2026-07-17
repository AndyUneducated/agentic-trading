"""运行配置加载（非密钥参数）。

统一从 `configs/*.yaml` 加载**非密钥**运行参数：策略配置路径、日志、以及安全关键的
预交易风控限额（纳入版本控制，而非散落代码硬编码）。密钥与运行模式仍由 `.env`/`Settings`
权威（禁止两处真相冲突）。所有解析错误统一抛 `ConfigError`。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

from atrading.core.errors import ConfigError
from atrading.core.risk_limits import RiskLimits
from atrading.core.strategy_config import StrategyConfig


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: Literal["json", "console"] = "json"


class RunConfig(BaseModel):
    """一次运行的非密钥配置。`strategy` 为策略 YAML 的绝对路径（from_yaml 时已解析）。"""

    strategy: str
    risk: RiskLimits
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @classmethod
    def from_yaml(cls, path: str | Path) -> RunConfig:
        config_path = Path(path)
        try:
            data: Any = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as error:
            msg = f"读取运行配置失败: {path}: {error}"
            raise ConfigError(msg) from error
        if not isinstance(data, dict) or "strategy" not in data or "risk" not in data:
            msg = f"运行配置必须包含 strategy 与 risk: {path}"
            raise ConfigError(msg)
        # 策略路径相对运行配置文件所在目录解析，避免依赖 cwd。
        data["strategy"] = str((config_path.parent / data["strategy"]).resolve())
        try:
            return cls.model_validate(data)
        except ConfigError:
            raise
        except Exception as error:  # noqa: BLE001 — 统一转换为 ConfigError
            msg = f"运行配置非法: {path}: {error}"
            raise ConfigError(msg) from error

    def load_strategy(self) -> StrategyConfig:
        return StrategyConfig.from_yaml(self.strategy)
