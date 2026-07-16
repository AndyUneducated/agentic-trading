"""LLM 信号层的结构化输出 schema（M4 据此产出，EVAL 据此打分）。

红线：LLM 只产信号，不下单。`as_of` 必须带时区（PIT）。schema 可版本化演进。
`to_signals()` 把结构化 schema 映射为通用 `Signal` 记录，供决策层/评测消费。
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field

from atrading.core.types import Signal


class EventFlag(StrEnum):
    none = "none"
    earnings = "earnings"
    guidance = "guidance"
    mna = "mna"
    macro = "macro"


class SignalSchemaV1(BaseModel):
    schema_version: Literal["v1"] = "v1"
    symbol: str
    as_of: AwareDatetime
    sentiment: float = Field(ge=-1, le=1)
    event_flag: EventFlag = EventFlag.none
    horizon_days: int = Field(ge=1, le=30)
    confidence: float = Field(ge=0, le=1)
    model_version: str
    prompt_version: str
    rationale: str

    def to_signals(self) -> list[Signal]:
        return [
            Signal(
                symbol=self.symbol,
                as_of=self.as_of,
                name="sentiment",
                value=self.sentiment,
                confidence=self.confidence,
                model_version=self.model_version,
                prompt_version=self.prompt_version,
                rationale=self.rationale,
            )
        ]
