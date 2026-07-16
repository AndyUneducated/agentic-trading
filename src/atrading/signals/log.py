"""信号留痕与成本记录。

每条信号连同模型/prompt 版本、推理理由、token/成本、可疑注入计数落盘（jsonl），
满足"100% 信号可追溯"与成本预算门。成本可聚合到日/月对照 CHARTER 预算。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import AwareDatetime, BaseModel, Field

from atrading.signals.extractor import ExtractionResult


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


class SignalLogEntry(BaseModel):
    logged_at: AwareDatetime = Field(default_factory=_utcnow)
    symbol: str
    as_of: AwareDatetime
    sentiment: float
    confidence: float
    event_flag: str
    horizon_days: int
    model_version: str
    prompt_version: str
    cost_usd: float
    input_tokens: int
    output_tokens: int
    suspicious_documents: int
    cache_hit: bool
    rationale: str

    @classmethod
    def from_result(cls, result: ExtractionResult) -> SignalLogEntry:
        signal = result.signal
        return cls(
            symbol=signal.symbol,
            as_of=signal.as_of,
            sentiment=signal.sentiment,
            confidence=signal.confidence,
            event_flag=signal.event_flag.value,
            horizon_days=signal.horizon_days,
            model_version=signal.model_version,
            prompt_version=signal.prompt_version,
            cost_usd=result.cost_usd,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            suspicious_documents=result.suspicious_documents,
            cache_hit=result.cache_hit,
            rationale=signal.rationale,
        )


class SignalLog:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def record(self, result: ExtractionResult) -> SignalLogEntry:
        entry = SignalLogEntry.from_result(result)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry.model_dump(mode="json"), ensure_ascii=False) + "\n")
        return entry

    def entries(self) -> list[SignalLogEntry]:
        if not self._path.exists():
            return []
        out: list[SignalLogEntry] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(SignalLogEntry.model_validate_json(line))
        return out

    def total_cost(self) -> float:
        return sum(entry.cost_usd for entry in self.entries())
