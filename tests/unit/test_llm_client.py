from __future__ import annotations

from atrading.core.signal_schema import EventFlag
from atrading.signals import KeywordLLMClient, parse_signal_draft


def test_keyword_client_is_deterministic() -> None:
    client = KeywordLLMClient()
    a = client.complete(system="s", user="strong growth and record profit")
    b = client.complete(system="s", user="strong growth and record profit")
    assert a.text == b.text
    assert a.model == "offline-keyword-v1"


def test_positive_and_negative_sentiment_sign() -> None:
    client = KeywordLLMClient()
    pos = parse_signal_draft(client.complete(system="", user="beat strong surge profit").text)
    neg = parse_signal_draft(client.complete(system="", user="miss weak plunge loss").text)
    assert pos.sentiment > 0
    assert neg.sentiment < 0


def test_neutral_when_no_lexicon_hits() -> None:
    client = KeywordLLMClient()
    draft = parse_signal_draft(client.complete(system="", user="the company held a meeting").text)
    assert draft.sentiment == 0.0
    assert draft.confidence == 0.0


def test_event_detection_and_cost() -> None:
    client = KeywordLLMClient(usd_per_1k_tokens=1.0)
    response = client.complete(system="", user="quarterly earnings eps revenue beat")
    draft = parse_signal_draft(response.text)
    assert draft.event_flag == EventFlag.earnings
    assert draft.horizon_days == 5
    assert response.cost_usd > 0
