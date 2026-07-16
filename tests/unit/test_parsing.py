from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from atrading.signals import parse_signal_draft


def test_parse_valid_draft() -> None:
    text = json.dumps(
        {
            "sentiment": 0.5,
            "event_flag": "earnings",
            "horizon_days": 5,
            "confidence": 0.8,
            "rationale": "ok",
        }
    )
    draft = parse_signal_draft(text)
    assert draft.sentiment == 0.5
    assert draft.horizon_days == 5


def test_parse_invalid_json_raises() -> None:
    with pytest.raises(json.JSONDecodeError):
        parse_signal_draft("not json {")


def test_parse_out_of_range_raises() -> None:
    text = json.dumps({"sentiment": 2.0, "horizon_days": 5, "confidence": 0.5, "rationale": "x"})
    with pytest.raises(ValidationError):
        parse_signal_draft(text)
