from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from atrading.core.types import Bar
from atrading.data import PITStore


def _bar(symbol: str, day: int, close: float) -> Bar:
    ts = datetime(2026, 1, day, tzinfo=UTC)
    return Bar(symbol=symbol, ts=ts, open=close, high=close, low=close, close=close, volume=10.0)


def test_roundtrip_and_pit_as_of(tmp_path: Path) -> None:
    store = PITStore(tmp_path)
    store.write_bars([_bar("A", 1, 100.0), _bar("A", 2, 110.0), _bar("A", 3, 121.0)], "daily")

    all_bars = store.read_bars(
        ["A"],
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 3, tzinfo=UTC),
        "daily",
        as_of=datetime(2026, 1, 3, tzinfo=UTC),
    )
    assert [b.close for b in all_bars] == [100.0, 110.0, 121.0]
    assert all(b.ts.tzinfo is not None for b in all_bars)

    pit_bars = store.read_bars(
        ["A"],
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 3, tzinfo=UTC),
        "daily",
        as_of=datetime(2026, 1, 2, tzinfo=UTC),
    )
    assert [b.ts.day for b in pit_bars] == [1, 2]


def test_incremental_write_appends_and_upserts(tmp_path: Path) -> None:
    # 回归：增量写入不得覆盖历史；相同 ts 的重复写入按最新值订正。
    store = PITStore(tmp_path)
    store.write_bars([_bar("A", 1, 100.0), _bar("A", 2, 110.0)], "daily")
    store.write_bars([_bar("A", 2, 111.0), _bar("A", 3, 121.0)], "daily")  # day2 订正 + day3 新增

    bars = store.read_bars(
        ["A"],
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 3, tzinfo=UTC),
        "daily",
        as_of=datetime(2026, 1, 3, tzinfo=UTC),
    )
    assert [(b.ts.day, b.close) for b in bars] == [(1, 100.0), (2, 111.0), (3, 121.0)]


def test_read_missing_symbol_returns_empty(tmp_path: Path) -> None:
    store = PITStore(tmp_path)
    result = store.read_bars(
        ["GHOST"],
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 3, tzinfo=UTC),
        "daily",
        as_of=datetime(2026, 1, 3, tzinfo=UTC),
    )
    assert result == []
