"""执行成本模型（M8）：手续费 + 滑点/市场冲击。

纯函数式、可被回测与实盘 broker **共用**（ADR-0003：回测-实盘同源，drift 只应来自真实
摩擦）。把成本从"bps 换手近似"升级为可分解、可校准的模型：
- CommissionModel：每股 + 按名义 bps + 每单下限。
- SlippageModel：固定 bps + 与参与率线性的市场冲击（下单越大、占成交量越多，滑点越大）。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

_BPS = 1e4


class CommissionModel(BaseModel):
    per_share: float = Field(default=0.0, ge=0)
    bps: float = Field(default=0.0, ge=0)  # 按名义额的基点
    min_per_order: float = Field(default=0.0, ge=0)

    def commission(self, qty: float, price: float) -> float:
        """qty 为成交股数（>0），price 为成交价。返回该笔的手续费（>=0）。"""
        if qty <= 0:
            return 0.0
        fee = qty * self.per_share + abs(qty * price) * self.bps / _BPS
        return max(fee, self.min_per_order)


class SlippageModel(BaseModel):
    bps: float = Field(default=0.0, ge=0)  # 固定滑点（基点）
    impact_bps_per_participation: float = Field(default=0.0, ge=0)  # 每 100% 参与率的额外基点

    def fill_price(self, side: str, mid: float, *, participation: float = 0.0) -> float:
        """买入向上滑、卖出向下滑；参与率越高冲击越大。participation∈[0,1]。"""
        total_bps = self.bps + self.impact_bps_per_participation * max(0.0, participation)
        adjustment = mid * total_bps / _BPS
        return mid + adjustment if side == "buy" else mid - adjustment
