"""防篡改审计追踪（M10 合规）。

每笔交易全量留痕（触发信号 → 决策依据 → 订单 → 成交），并用**哈希链**串联：任一历史
记录被改动，`verify()` 即失败（tamper-evident）。满足"每笔交易可复盘"的合规要件。
可选 jsonl 持久化以跨进程/长期留存。
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import AwareDatetime, BaseModel

from atrading.core.types import Fill, Order

_GENESIS = "0" * 64


class AuditRecord(BaseModel):
    seq: int
    ts: AwareDatetime
    kind: str  # signal|decision|order|fill|risk_denial|stage_change|...
    payload: dict[str, Any]
    prev_hash: str
    hash: str


def _compute_hash(
    prev_hash: str, seq: int, ts: datetime, kind: str, payload: dict[str, Any]
) -> str:
    body = json.dumps(
        {
            "prev": prev_hash,
            "seq": seq,
            "ts": ts.isoformat(),
            "kind": kind,
            "payload": payload,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


class AuditTrail:
    def __init__(self, path: str | Path | None = None) -> None:
        self._records: list[AuditRecord] = []
        self._path = Path(path) if path is not None else None
        if self._path is not None and self._path.exists():
            self._load()

    def _load(self) -> None:
        assert self._path is not None
        for line in self._path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                self._records.append(AuditRecord.model_validate_json(line))

    def append(self, kind: str, payload: dict[str, Any], *, ts: datetime) -> AuditRecord:
        prev = self._records[-1].hash if self._records else _GENESIS
        seq = len(self._records)
        record = AuditRecord(
            seq=seq,
            ts=ts,
            kind=kind,
            payload=payload,
            prev_hash=prev,
            hash=_compute_hash(prev, seq, ts, kind, payload),
        )
        self._records.append(record)
        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(record.model_dump_json() + "\n")
        return record

    def record_order(self, order: Order, *, ts: datetime) -> AuditRecord:
        return self.append("order", order.model_dump(mode="json"), ts=ts)

    def record_fill(self, fill: Fill) -> AuditRecord:
        return self.append("fill", fill.model_dump(mode="json"), ts=fill.ts)

    def verify(self) -> bool:
        """重算哈希链，任一记录被篡改/乱序/断链 → False。"""
        prev = _GENESIS
        for index, record in enumerate(self._records):
            if record.seq != index or record.prev_hash != prev:
                return False
            expected = _compute_hash(prev, record.seq, record.ts, record.kind, record.payload)
            if expected != record.hash:
                return False
            prev = record.hash
        return True

    def records(self) -> list[AuditRecord]:
        return list(self._records)
