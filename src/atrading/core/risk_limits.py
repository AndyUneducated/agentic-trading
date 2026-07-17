"""预交易风控限额（纯配置模型）。

放在 core 层，使配置层（RunConfig）与风控层（PreTradeRiskGate）都能引用而不产生循环
依赖。金额字段以名义美元计；`daily_loss_limit` 为占日初权益的比例。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from atrading.core.errors import ConfigError


class RiskLimits(BaseModel):
    max_position_per_name: float = Field(gt=0)  # 单标的名义上限（金额）
    max_gross_exposure: float = Field(gt=0)  # 总名义敞口上限（金额）
    max_notional_per_order: float = Field(gt=0)  # 单笔名义上限（金额）
    max_orders_per_interval: int = Field(gt=0)  # 单个决策周期最多下单数
    daily_loss_limit: float = Field(gt=0, le=1)  # 日内亏损熔断（占日初权益比例）

    @classmethod
    def from_yaml(cls, path: str | Path) -> RiskLimits:
        """从 YAML 加载（安全关键参数纳入版本控制，而非散落代码硬编码）。"""
        try:
            data: Any = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as error:
            msg = f"读取风控配置失败: {path}: {error}"
            raise ConfigError(msg) from error
        try:
            return cls.model_validate(data)
        except Exception as error:  # noqa: BLE001 — 统一转换为 ConfigError
            msg = f"风控配置非法: {path}: {error}"
            raise ConfigError(msg) from error
