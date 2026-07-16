from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from atrading.execution import EngineState, FileStateStore


def test_save_load_roundtrip(tmp_path: Path) -> None:
    store = FileStateStore(tmp_path / "state.json")
    state = EngineState(
        positions={"AAA": 5.0},
        cash=999.0,
        submitted_order_ids=["x", "y"],
        last_ts=datetime(2026, 1, 2, tzinfo=UTC),
        day_start_equity=100_000.0,
    )
    store.save(state)

    loaded = store.load()
    assert loaded is not None
    assert loaded.positions == {"AAA": 5.0}
    assert loaded.submitted_order_ids == ["x", "y"]
    assert loaded.day_start_equity == 100_000.0


def test_load_missing_returns_none(tmp_path: Path) -> None:
    assert FileStateStore(tmp_path / "nope.json").load() is None
