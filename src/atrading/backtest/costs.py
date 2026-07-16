"""交易成本模型（真实摩擦）。

很多回测框架默认零成本，会系统性高估收益。这里显式建模手续费 + 滑点，
按换手（turnover，占权益比例）折算为收益率损耗。参数化且有默认值。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CostModel(BaseModel):
    commission_bps: float = Field(default=1.0, ge=0)
    slippage_bps: float = Field(default=5.0, ge=0)

    def cost_fraction(self, turnover: float) -> float:
        """给定换手率（Σ|Δw|，占权益比例），返回本次再平衡的权益损耗比例。"""
        return (self.commission_bps + self.slippage_bps) / 1e4 * turnover
