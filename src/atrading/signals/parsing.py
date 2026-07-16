"""结构化解析：LLM 文本 → SignalDraft。

SignalDraft 是"LLM 决定的部分"（情绪/事件/置信/时域/理由）。提取器随后补齐
symbol/as_of/model_version/prompt_version，提升为 SignalSchemaV1。坏输出（非法 JSON /
缺字段 / 越界）会抛错，交由提取器重试。
"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from atrading.core.signal_schema import EventFlag

SIGNAL_DRAFT_SCHEMA = "SignalDraft"


class SignalDraft(BaseModel):
    sentiment: float = Field(ge=-1, le=1)
    event_flag: EventFlag = EventFlag.none
    horizon_days: int = Field(ge=1, le=30)
    confidence: float = Field(ge=0, le=1)
    rationale: str


def parse_signal_draft(text: str) -> SignalDraft:
    """解析结构化输出；非法 JSON 抛 json.JSONDecodeError，schema 违规抛 ValidationError。"""
    data = json.loads(text)
    return SignalDraft.model_validate(data)
