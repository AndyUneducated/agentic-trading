from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from atrading.signals import Document, KeywordLLMClient, SentimentExtractor, load_prompt
from atrading.signals.log import SignalLog


def _prompt():  # type: ignore[no-untyped-def]
    return load_prompt("sentiment", "v1", expected_schema="SignalDraft")


def test_log_records_and_aggregates_cost(tmp_path: Path) -> None:
    extractor = SentimentExtractor(KeywordLLMClient(usd_per_1k_tokens=1.0), _prompt())
    log = SignalLog(tmp_path / "signals.jsonl")

    for day in (1, 2):
        result = extractor.extract(
            symbol="AAPL",
            as_of=datetime(2026, 1, day, tzinfo=UTC),
            documents=[
                Document(
                    source_id="s",
                    symbol="AAPL",
                    published_at=datetime(2026, 1, 1, tzinfo=UTC),
                    text="strong growth record profit",
                )
            ],
        )
        log.record(result)

    entries = log.entries()
    assert len(entries) == 2
    assert all(entry.model_version == "offline-keyword-v1" for entry in entries)
    assert all(entry.rationale for entry in entries)  # 100% 有推理留痕
    assert log.total_cost() > 0
