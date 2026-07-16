from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from atrading.signals import (
    Document,
    LLMResponse,
    SentimentExtractor,
    SignalCache,
    input_fingerprint,
    load_prompt,
)


def _doc(text: str, source: str = "s") -> Document:
    return Document(
        source_id=source, symbol="AAPL", published_at=datetime(2026, 1, 1, tzinfo=UTC), text=text
    )


def test_fingerprint_changes_with_documents() -> None:
    kwargs = {
        "prompt_name": "sentiment",
        "prompt_version": "v1",
        "symbol": "AAPL",
        "as_of": datetime(2026, 1, 2, tzinfo=UTC),
    }
    fp1 = input_fingerprint(documents=[_doc("a")], **kwargs)  # type: ignore[arg-type]
    fp2 = input_fingerprint(documents=[_doc("b")], **kwargs)  # type: ignore[arg-type]
    fp1_again = input_fingerprint(documents=[_doc("a")], **kwargs)  # type: ignore[arg-type]
    assert fp1 != fp2
    assert fp1 == fp1_again


class CountingClient:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, *, system: str, user: str, temperature: float = 0.0) -> LLMResponse:
        self.calls += 1
        text = json.dumps(
            {
                "sentiment": 0.2,
                "event_flag": "none",
                "horizon_days": 7,
                "confidence": 0.5,
                "rationale": "r",
            }
        )
        return LLMResponse(text=text, model="c", input_tokens=1, output_tokens=1, cost_usd=0.01)


def test_cache_hit_avoids_second_call() -> None:
    client = CountingClient()
    cache = SignalCache()
    extractor = SentimentExtractor(client, _p(), cache=cache)
    args = {"symbol": "AAPL", "as_of": datetime(2026, 1, 2, tzinfo=UTC), "documents": [_doc("x")]}

    first = extractor.extract(**args)  # type: ignore[arg-type]
    second = extractor.extract(**args)  # type: ignore[arg-type]

    assert client.calls == 1
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert second.signal.sentiment == first.signal.sentiment


def test_cache_persists_to_disk(tmp_path: Path) -> None:
    path = tmp_path / "cache.jsonl"
    extractor = SentimentExtractor(CountingClient(), _p(), cache=SignalCache(path))
    extractor.extract(symbol="AAPL", as_of=datetime(2026, 1, 2, tzinfo=UTC), documents=[_doc("x")])

    reloaded = SignalCache(path)
    client = CountingClient()
    extractor2 = SentimentExtractor(client, _p(), cache=reloaded)
    result = extractor2.extract(
        symbol="AAPL", as_of=datetime(2026, 1, 2, tzinfo=UTC), documents=[_doc("x")]
    )
    assert result.cache_hit is True
    assert client.calls == 0


def _p():  # type: ignore[no-untyped-def]
    return load_prompt("sentiment", "v1", expected_schema="SignalDraft")
