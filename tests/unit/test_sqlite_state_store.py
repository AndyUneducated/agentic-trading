from __future__ import annotations

from pathlib import Path

from atrading.execution import EngineState, SQLiteStateStore


def test_save_then_load_roundtrip(tmp_path: Path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db", namespace="a")
    assert store.load() is None
    store.save(EngineState(cash=123.0, positions={"X": 1.0}))
    loaded = store.load()
    assert loaded is not None
    assert loaded.cash == 123.0
    assert loaded.positions == {"X": 1.0}


def test_namespace_isolation(tmp_path: Path) -> None:
    db = tmp_path / "state.db"
    store_a = SQLiteStateStore(db, namespace="alpha")
    store_b = SQLiteStateStore(db, namespace="beta")
    store_a.save(EngineState(cash=1.0))
    store_b.save(EngineState(cash=2.0))
    loaded_a = store_a.load()
    loaded_b = store_b.load()
    assert loaded_a is not None and loaded_a.cash == 1.0
    assert loaded_b is not None and loaded_b.cash == 2.0


def test_upsert_overwrites(tmp_path: Path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    store.save(EngineState(cash=1.0))
    store.save(EngineState(cash=9.0))
    loaded = store.load()
    assert loaded is not None and loaded.cash == 9.0
