"""LLMSignalSource：把已产信号接入 core.SignalSource，供 M3 回测 / M5 执行消费。

回测通常**离线预生成**信号库（确定性、低成本重放）：一次性抽取好的 SignalSchemaV1
放入本 source，`signals_as_of` 只返回 as_of<=ts 的信号（PIT）。
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from atrading.core.signal_schema import SignalSchemaV1
from atrading.core.types import Signal
from atrading.signals.extractor import ExtractionResult


class LLMSignalSource:
    def __init__(self, signals: Iterable[SignalSchemaV1]) -> None:
        self._schemas = list(signals)

    @classmethod
    def from_results(cls, results: Iterable[ExtractionResult]) -> LLMSignalSource:
        return cls(result.signal for result in results)

    def signals_as_of(self, ts: datetime, symbols: list[str]) -> list[Signal]:
        wanted = set(symbols)
        out: list[Signal] = []
        for schema in self._schemas:
            if schema.symbol in wanted and schema.as_of <= ts:
                out.extend(schema.to_signals())
        return out
