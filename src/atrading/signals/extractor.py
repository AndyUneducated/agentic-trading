"""信号提取器：documents → SignalSchemaV1。

职责：PIT 过滤（只用 published_at<=as_of 的文档）、注入安全地渲染 prompt、调用
LLMClient 并带重试地解析结构化输出，最后由**提取器**（而非 LLM）补齐 symbol/as_of/
model_version/prompt_version，保证 PIT 与留痕正确。可选缓存以复现与省钱。

一个提取器对应一类信号；新增信号 = 新提取器 + 新 prompt。
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime

from pydantic import BaseModel, ValidationError

from atrading.core.signal_schema import SignalSchemaV1
from atrading.monitoring.metrics import MetricsRegistry
from atrading.signals.cache import SignalCache, input_fingerprint
from atrading.signals.documents import Document
from atrading.signals.llm_client import LLMClient
from atrading.signals.parsing import SignalDraft, parse_signal_draft
from atrading.signals.prompts import PromptTemplate
from atrading.signals.sanitize import build_documents_block


class ExtractionResult(BaseModel):
    signal: SignalSchemaV1
    cost_usd: float
    input_tokens: int
    output_tokens: int
    suspicious_documents: int
    cache_hit: bool


class SentimentExtractor:
    def __init__(
        self,
        client: LLMClient,
        prompt: PromptTemplate,
        *,
        max_retries: int = 2,
        cache: SignalCache | None = None,
        metrics: MetricsRegistry | None = None,
    ) -> None:
        self._client = client
        self._prompt = prompt
        self._max_retries = max_retries
        self._cache = cache
        self._metrics = metrics

    def extract(
        self, *, symbol: str, as_of: datetime, documents: Sequence[Document]
    ) -> ExtractionResult:
        pit_docs = [doc for doc in documents if doc.published_at <= as_of]

        fingerprint = input_fingerprint(
            prompt_name=self._prompt.name,
            prompt_version=self._prompt.version,
            symbol=symbol,
            as_of=as_of,
            documents=pit_docs,
        )
        if self._cache is not None:
            cached = self._cache.get(fingerprint)
            if cached is not None:
                if self._metrics is not None:
                    self._metrics.inc("atrading_signal_cache_total", result="hit")
                return ExtractionResult(
                    signal=cached,
                    cost_usd=0.0,
                    input_tokens=0,
                    output_tokens=0,
                    suspicious_documents=0,
                    cache_hit=True,
                )

        block, suspicious = build_documents_block(pit_docs)
        system, user = self._prompt.render(symbol=symbol, as_of=as_of, documents_block=block)
        draft, model, cost, in_tok, out_tok = self._call_with_retry(system, user)
        self._record_extraction(
            model=model, cost=cost, in_tok=in_tok, out_tok=out_tok, suspicious=suspicious
        )

        signal = SignalSchemaV1(
            symbol=symbol,
            as_of=as_of,
            sentiment=draft.sentiment,
            event_flag=draft.event_flag,
            horizon_days=draft.horizon_days,
            confidence=draft.confidence,
            model_version=model,
            prompt_version=self._prompt.version,
            rationale=draft.rationale,
        )
        if self._cache is not None:
            self._cache.set(fingerprint, signal)

        return ExtractionResult(
            signal=signal,
            cost_usd=cost,
            input_tokens=in_tok,
            output_tokens=out_tok,
            suspicious_documents=suspicious,
            cache_hit=False,
        )

    def _record_extraction(
        self, *, model: str, cost: float, in_tok: int, out_tok: int, suspicious: int
    ) -> None:
        if self._metrics is None:
            return
        self._metrics.inc("atrading_signal_cache_total", result="miss")
        self._metrics.inc("atrading_llm_cost_usd_total", cost, model=model)
        self._metrics.inc("atrading_llm_tokens_total", float(in_tok), kind="input")
        self._metrics.inc("atrading_llm_tokens_total", float(out_tok), kind="output")
        if suspicious:
            self._metrics.inc("atrading_suspicious_docs_total", float(suspicious))

    def _call_with_retry(self, system: str, user: str) -> tuple[SignalDraft, str, float, int, int]:
        last_error: Exception | None = None
        model = "unknown"
        total_cost = 0.0
        total_in = 0
        total_out = 0
        for _ in range(self._max_retries + 1):
            response = self._client.complete(system=system, user=user, temperature=0.0)
            model = response.model
            total_cost += response.cost_usd
            total_in += response.input_tokens
            total_out += response.output_tokens
            try:
                draft = parse_signal_draft(response.text)
            except (json.JSONDecodeError, ValidationError) as error:
                last_error = error
                continue
            return draft, model, total_cost, total_in, total_out
        msg = f"结构化解析在 {self._max_retries + 1} 次尝试后仍失败"
        raise ValueError(msg) from last_error
