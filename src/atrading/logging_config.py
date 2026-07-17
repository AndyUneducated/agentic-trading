"""结构化日志配置（structlog）。

统一留痕格式：默认 JSON（机器可解析、便于审计与后续接入日志系统），可用
`--log-format console` 或 `ATRADING_LOG_FORMAT=console` 切换为人类可读。运行时逻辑
应通过 `get_logger()` 记录事件，而非散落 `print`（决策/交易留痕是本项目一等公民）。
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

import structlog


def configure_logging(*, level: str = "INFO", fmt: str | None = None) -> None:
    """进程级一次性配置。fmt ∈ {json, console}；缺省读 ATRADING_LOG_FORMAT，默认 json。"""
    resolved_fmt = fmt or os.getenv("ATRADING_LOG_FORMAT", "json")
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=log_level)

    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    if resolved_fmt == "console":
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "atrading") -> Any:
    """返回绑定名字的 structlog logger（薄封装，类型有意放宽为 Any）。"""
    return structlog.get_logger(name)
