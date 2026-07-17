from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from atrading.core.types import Fill, Order
from atrading.governance.audit import AuditTrail

_TS = datetime(2026, 1, 1, tzinfo=UTC)


def test_hash_chain_verifies() -> None:
    trail = AuditTrail()
    trail.append("signal", {"symbol": "AAPL", "sentiment": 0.8}, ts=_TS)
    trail.append("decision", {"weights": {"AAPL": 1.0}}, ts=_TS)
    trail.record_order(Order(symbol="AAPL", side="buy", qty=10, client_order_id="o1"), ts=_TS)
    trail.record_fill(Fill(client_order_id="o1", symbol="AAPL", qty=10, price=100.0, ts=_TS))
    assert len(trail.records()) == 4
    assert trail.verify()


def test_tamper_detected() -> None:
    trail = AuditTrail()
    trail.append("signal", {"symbol": "AAPL", "sentiment": 0.8}, ts=_TS)
    trail.append("order", {"qty": 10}, ts=_TS)
    # 篡改历史 payload → 哈希链断裂
    trail.records()  # snapshot 不影响内部
    trail._records[0].payload["sentiment"] = -0.8  # noqa: SLF001 — 测试直接改内部模拟篡改
    assert not trail.verify()


def test_persistence_roundtrip_and_chain(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    trail = AuditTrail(path)
    trail.append("signal", {"symbol": "AAPL"}, ts=_TS)
    trail.append("order", {"qty": 5}, ts=_TS)

    reloaded = AuditTrail(path)  # 从磁盘恢复
    assert len(reloaded.records()) == 2
    assert reloaded.verify()
    reloaded.append("fill", {"qty": 5}, ts=_TS)  # 续链
    assert reloaded.verify()
