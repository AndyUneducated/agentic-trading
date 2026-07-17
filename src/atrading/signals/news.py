"""新闻/文档数据源（M7）：带 Point-in-Time 时序隔离。

头号红线：回测时只能看到"当时已发布"的文档（`published_at <= as_of`）。以时间为
过滤主键，杜绝 RAG 前视泄漏（把未来新闻当历史用会让 Sharpe 作废）。真实源（新闻/
财报 API）按同一接口实现，替换内存实现即可。
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from atrading.signals.documents import Document


class NewsSource(Protocol):
    def documents_as_of(self, ts: datetime, symbols: Sequence[str]) -> list[Document]: ...


class InMemoryNewsSource:
    """内存实现：便于测试与离线跑通。真实 API 适配按 NewsSource 协议替换。"""

    def __init__(self, documents: Sequence[Document]) -> None:
        self._docs = list(documents)

    def documents_as_of(self, ts: datetime, symbols: Sequence[str]) -> list[Document]:
        wanted = set(symbols)
        out = [
            doc
            for doc in self._docs
            if doc.symbol in wanted and doc.published_at <= ts  # PIT：只见已发布
        ]
        out.sort(key=lambda d: (d.symbol, d.published_at, d.source_id))
        return out
