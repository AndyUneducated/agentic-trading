from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from atrading.core.signal_schema import EventFlag, SignalSchemaV1


def _valid_kwargs() -> dict[str, object]:
    return {
        "symbol": "AAPL",
        "as_of": datetime(2026, 1, 1, tzinfo=UTC),
        "sentiment": 0.5,
        "event_flag": EventFlag.earnings,
        "horizon_days": 5,
        "confidence": 0.8,
        "model_version": "deepseek-chat",
        "prompt_version": "sentiment/v1",
        "rationale": "positive guidance",
    }


def test_valid_schema_and_to_signals() -> None:
    sig = SignalSchemaV1(**_valid_kwargs())
    assert sig.schema_version == "v1"
    signals = sig.to_signals()
    assert len(signals) == 1
    assert signals[0].name == "sentiment"
    assert signals[0].value == 0.5
    assert signals[0].prompt_version == "sentiment/v1"


def test_sentiment_out_of_range_rejected() -> None:
    kwargs = _valid_kwargs()
    kwargs["sentiment"] = 1.5
    with pytest.raises(ValidationError):
        SignalSchemaV1(**kwargs)


def test_horizon_out_of_range_rejected() -> None:
    kwargs = _valid_kwargs()
    kwargs["horizon_days"] = 999
    with pytest.raises(ValidationError):
        SignalSchemaV1(**kwargs)


def test_naive_as_of_rejected() -> None:
    kwargs = _valid_kwargs()
    kwargs["as_of"] = datetime(2026, 1, 1)  # naive
    with pytest.raises(ValidationError):
        SignalSchemaV1(**kwargs)
