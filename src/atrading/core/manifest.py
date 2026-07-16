"""可复现元数据规范（Run Manifest）。

每次回测/评测/实验运行都应产出一个 manifest，记录复现所需的一切：
git commit、数据/代码版本、随机种子、模型/prompt 版本、参数。
产物统一写入 `runs/<run_id>/`（已被 .gitignore 忽略），并附 `manifest.json`。
"""

from __future__ import annotations

import subprocess
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(UTC)


def current_git_commit() -> str:
    """返回当前 git commit 短哈希；不可用时返回 'unknown'（不抛错）。"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"
    return result.stdout.strip() or "unknown"


class RunManifest(BaseModel):
    run_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    created_at: datetime = Field(default_factory=_utcnow)
    git_commit: str = Field(default_factory=current_git_commit)
    data_version: str = "unknown"
    code_version: str = "0.0.0"
    seed: int = 0
    llm_model: str | None = None
    prompt_version: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
