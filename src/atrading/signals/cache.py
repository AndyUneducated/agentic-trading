"""信号缓存：输入指纹 → 已产信号。

命中则不重复调用 LLM（省钱 + 可复现）。指纹覆盖 prompt 名/版本、symbol、as_of 与
文档内容哈希——任一变化都会 miss 并重算。可选 jsonl 持久化以跨进程复用。
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from atrading.core.signal_schema import SignalSchemaV1
from atrading.signals.documents import Document


def input_fingerprint(
    *,
    prompt_name: str,
    prompt_version: str,
    symbol: str,
    as_of: datetime,
    documents: Sequence[Document],
) -> str:
    doc_hashes = sorted(
        hashlib.sha256(f"{doc.source_id}|{doc.text}".encode()).hexdigest() for doc in documents
    )
    payload = json.dumps(
        {
            "prompt": prompt_name,
            "version": prompt_version,
            "symbol": symbol,
            "as_of": as_of.isoformat(),
            "docs": doc_hashes,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


class SignalCache:
    def __init__(self, path: str | Path | None = None) -> None:
        self._mem: dict[str, SignalSchemaV1] = {}
        self._path = Path(path) if path is not None else None
        if self._path is not None and self._path.exists():
            self._load()

    def _load(self) -> None:
        assert self._path is not None
        for line in self._path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            self._mem[record["fingerprint"]] = SignalSchemaV1.model_validate(record["signal"])

    def get(self, fingerprint: str) -> SignalSchemaV1 | None:
        return self._mem.get(fingerprint)

    def set(self, fingerprint: str, signal: SignalSchemaV1) -> None:
        self._mem[fingerprint] = signal
        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            record = {"fingerprint": fingerprint, "signal": signal.model_dump(mode="json")}
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
