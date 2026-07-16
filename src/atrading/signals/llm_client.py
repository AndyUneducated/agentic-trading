"""供应商无关的 LLM 客户端接口 + 离线确定性 stub 后端。

`LLMClient` 是真实后端（OpenAI/Anthropic/DeepSeek/Ollama）与离线 stub 共同实现的协议。
本机算力/预算受限时，用 `KeywordLLMClient`（基于词典打分、零网络、完全确定）跑通并测试
整条信号管线；真实后端后续按同一协议替换，无需改动提取器/评测。

红线：客户端只产文本/结构化信号，绝不下单（ADR-0001）。
"""

from __future__ import annotations

import json
import re
from typing import Protocol

from pydantic import BaseModel

from atrading.core.signal_schema import EventFlag


class LLMResponse(BaseModel):
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


class LLMClient(Protocol):
    """供应商无关：给定 system/user，返回文本 + 用量/成本。temperature 默认 0 以求可复现。"""

    def complete(self, *, system: str, user: str, temperature: float = 0.0) -> LLMResponse: ...


_POSITIVE = frozenset(
    {
        "beat",
        "beats",
        "strong",
        "growth",
        "surge",
        "surged",
        "upgrade",
        "upgraded",
        "record",
        "profit",
        "profits",
        "gain",
        "gains",
        "bullish",
        "outperform",
        "raise",
        "raised",
        "expand",
        "expands",
        "rally",
        "soar",
        "soared",
        "jump",
        "rise",
        "rose",
        "boost",
        "boosted",
        "win",
        "wins",
        "positive",
    }
)
_NEGATIVE = frozenset(
    {
        "miss",
        "misses",
        "missed",
        "weak",
        "decline",
        "declined",
        "plunge",
        "plunged",
        "downgrade",
        "downgraded",
        "loss",
        "losses",
        "cut",
        "cuts",
        "bearish",
        "underperform",
        "lawsuit",
        "investigation",
        "bankrupt",
        "bankruptcy",
        "warn",
        "warns",
        "warning",
        "fall",
        "fell",
        "drop",
        "dropped",
        "slump",
        "negative",
        "fraud",
        "recall",
        "layoff",
        "layoffs",
    }
)
_EVENT_WORDS: dict[EventFlag, frozenset[str]] = {
    EventFlag.earnings: frozenset({"earnings", "quarter", "quarterly", "eps", "revenue"}),
    EventFlag.guidance: frozenset({"guidance", "outlook", "forecast", "guide"}),
    EventFlag.mna: frozenset({"merger", "acquisition", "acquire", "takeover", "buyout"}),
    EventFlag.macro: frozenset({"fed", "inflation", "cpi", "gdp", "tariff"}),
}
_TOKEN = re.compile(r"[a-z']+")


class KeywordLLMClient:
    """离线确定性 stub：基于词典对 user 文本打分，产出 SignalDraft 形状的 JSON。

    不做任何网络调用，同一输入恒定同一输出（可复现）。它是一个纯数据处理器，
    不会"听从"文档里的指令——天然演示了指令/数据的隔离。
    """

    def __init__(self, model: str = "offline-keyword-v1", usd_per_1k_tokens: float = 0.0) -> None:
        self._model = model
        self._price = usd_per_1k_tokens

    def complete(self, *, system: str, user: str, temperature: float = 0.0) -> LLMResponse:
        tokens = _TOKEN.findall(user.lower())
        pos = sum(token in _POSITIVE for token in tokens)
        neg = sum(token in _NEGATIVE for token in tokens)
        total = pos + neg
        sentiment = 0.0 if total == 0 else round((pos - neg) / total, 4)
        confidence = 0.0 if total == 0 else round(min(1.0, total / 5.0), 4)
        event_flag, horizon_days = self._detect_event(tokens)

        draft = {
            "sentiment": sentiment,
            "event_flag": event_flag.value,
            "horizon_days": horizon_days,
            "confidence": confidence,
            "rationale": f"pos={pos} neg={neg} event={event_flag.value}",
        }
        text = json.dumps(draft, ensure_ascii=False, sort_keys=True)
        input_tokens = len(tokens)
        output_tokens = len(text.split())
        cost = round((input_tokens + output_tokens) / 1000.0 * self._price, 6)
        return LLMResponse(
            text=text,
            model=self._model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
        )

    @staticmethod
    def _detect_event(tokens: list[str]) -> tuple[EventFlag, int]:
        token_set = set(tokens)
        best = EventFlag.none
        best_hits = 0
        for flag, words in _EVENT_WORDS.items():
            hits = len(token_set & words)
            if hits > best_hits:
                best, best_hits = flag, hits
        horizon = 5 if best in (EventFlag.earnings, EventFlag.guidance) else 10
        return best, horizon
