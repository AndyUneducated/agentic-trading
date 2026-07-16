"""非结构化输入文档。

每个 Document 带 `published_at`（PIT：提取时只用 published_at<=as_of 的文档）
与可追溯的 `source_id`。文档正文视为**不可信数据**（见 sanitize）。
"""

from __future__ import annotations

from pydantic import AwareDatetime, BaseModel


class Document(BaseModel):
    source_id: str
    symbol: str
    published_at: AwareDatetime
    text: str
