from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from atrading.signals import load_prompt
from atrading.signals.prompts import DEFAULT_PROMPTS_ROOT


def test_load_sentiment_v1() -> None:
    prompt = load_prompt("sentiment", "v1", expected_schema="SignalDraft")
    assert prompt.version == "v1"
    assert "never place orders" in prompt.system.lower()
    assert "{{DOCUMENTS}}" in prompt.user_template


def test_render_fills_placeholders() -> None:
    prompt = load_prompt("sentiment", "v1", expected_schema="SignalDraft")
    system, user = prompt.render(
        symbol="AAPL", as_of=datetime(2026, 1, 1, tzinfo=UTC), documents_block="<doc/>"
    )
    assert "AAPL" in user
    assert "<doc/>" in user
    assert "{{SYMBOL}}" not in user
    assert system == prompt.system


def test_schema_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="schema 不匹配"):
        load_prompt("sentiment", "v1", expected_schema="SomethingElse")


def test_missing_prompt_raises(tmp_path: Path) -> None:
    assert DEFAULT_PROMPTS_ROOT.name == "prompts"
    with pytest.raises(FileNotFoundError):
        load_prompt("ghost", "v9", expected_schema="SignalDraft", root=tmp_path)
