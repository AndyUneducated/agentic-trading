from __future__ import annotations

from datetime import UTC, datetime

from atrading.signals.documents import Document
from atrading.signals.news import InMemoryNewsSource


def _doc(symbol: str, day: int, text: str = "t", source: str = "s") -> Document:
    return Document(
        source_id=source,
        symbol=symbol,
        published_at=datetime(2026, 1, day, tzinfo=UTC),
        text=text,
    )


def test_pit_excludes_future_documents() -> None:
    source = InMemoryNewsSource([_doc("AAPL", 1), _doc("AAPL", 3)])
    visible = source.documents_as_of(datetime(2026, 1, 2, tzinfo=UTC), ["AAPL"])
    assert [d.published_at.day for d in visible] == [1]  # day3 是未来，被排除


def test_symbol_filter() -> None:
    source = InMemoryNewsSource([_doc("AAPL", 1), _doc("MSFT", 1)])
    visible = source.documents_as_of(datetime(2026, 1, 2, tzinfo=UTC), ["AAPL"])
    assert [d.symbol for d in visible] == ["AAPL"]


def test_deterministic_order() -> None:
    source = InMemoryNewsSource(
        [_doc("MSFT", 1, source="b"), _doc("AAPL", 1, source="a"), _doc("AAPL", 1, source="c")]
    )
    visible = source.documents_as_of(datetime(2026, 1, 5, tzinfo=UTC), ["AAPL", "MSFT"])
    assert [(d.symbol, d.source_id) for d in visible] == [
        ("AAPL", "a"),
        ("AAPL", "c"),
        ("MSFT", "b"),
    ]
