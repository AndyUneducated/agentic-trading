"""引擎状态持久化（crash-only 雏形）。

任何时刻被杀都能从持久化状态恢复：重启后 load() + 启动对账，配合幂等 client_order_id
保证不重复/不丢单。文件式 JSON 起步（原子写：写临时文件再 os.replace）。
"""

from __future__ import annotations

import json
import os
import tempfile
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
