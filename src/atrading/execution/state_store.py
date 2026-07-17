"""引擎状态持久化（crash-only 雏形）。

任何时刻被杀都能从持久化状态恢复：重启后 load() + 启动对账，配合幂等 client_order_id
保证不重复/不丢单。文件式 JSON 起步（原子写：写临时文件再 os.replace）。
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from pydantic import AwareDatetime, BaseModel, Field


class EngineState(BaseModel):
    positions: dict[str, float] = Field(default_factory=dict)
    cash: float = 0.0
    submitted_order_ids: list[str] = Field(default_factory=list)
    last_ts: AwareDatetime | None = None
    day_start_equity: float | None = None
    orders_this_interval: int = 0


class StateStore(Protocol):
    def save(self, state: EngineState) -> None: ...
    def load(self) -> EngineState | None: ...


class FileStateStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def save(self, state: EngineState) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(state.model_dump(mode="json"), ensure_ascii=False, indent=2)
        # 原子写：同目录临时文件 + os.replace（避免半写状态）。
        fd, tmp_name = tempfile.mkstemp(dir=str(self._path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            os.replace(tmp_name, self._path)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise

    def load(self) -> EngineState | None:
        if not self._path.exists():
            return None
        return EngineState.model_validate_json(self._path.read_text(encoding="utf-8"))


class SQLiteStateStore:
    """SQLite 持久化 StateStore：支持**多策略命名空间**、事务原子性与进程级并发安全。

    相比单 JSON 文件（`FileStateStore`）：多个策略/账户可共用一个 db，各自 `namespace`
    隔离；写入走 sqlite 的 upsert + 事务（崩溃不会留下半写状态）。
    """

    def __init__(self, path: str | Path, *, namespace: str = "default") -> None:
        self._path = Path(path)
        self._namespace = namespace
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS engine_state ("
                "namespace TEXT PRIMARY KEY, state_json TEXT NOT NULL, updated_at TEXT NOT NULL)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)

    def save(self, state: EngineState) -> None:
        payload = json.dumps(state.model_dump(mode="json"), ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO engine_state(namespace, state_json, updated_at) VALUES(?, ?, ?) "
                "ON CONFLICT(namespace) DO UPDATE SET "
                "state_json=excluded.state_json, updated_at=excluded.updated_at",
                (self._namespace, payload, datetime.now(tz=UTC).isoformat()),
            )

    def load(self) -> EngineState | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT state_json FROM engine_state WHERE namespace = ?",
                (self._namespace,),
            ).fetchone()
        if row is None:
            return None
        return EngineState.model_validate_json(row[0])
