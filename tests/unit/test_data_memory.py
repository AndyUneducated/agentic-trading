from __future__ import annotations

from datetime import UTC, datetime

from atrading.core.types import Bar
from atrading.data import InMemoryDataSource


def _bar(symbol: str, day: int) -> Bar:
    ts = datetime(2026, 1, day, tzinfo=UTC)
    return Bar(symbol=symbol, ts=ts, open=1, high=1, low=1, close=1, volume=1)


def test_get_bars_filters_symbol_and_window() -> None:
    src = InMemoryDataSource([_bar("A", 1), _bar("A", 2), _bar("A", 3), _bar("B", 2)])
    result = src.get_bars(
        ["A"], datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC), "daily"
    )
    assert [b.ts.day for b in result] == [1, 2]
    assert {b.symbol for b in result} == {"A"}
