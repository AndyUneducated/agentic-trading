"""轻量分布式追踪（M9）：零依赖 span，可选升级到 OpenTelemetry。

用 `with tracer.span("decide"):` 包裹关键路径（信号提取 / 决策 / 下单），记录耗时与
父子关系，便于定位"慢在哪一步"。本机算力有限，核心不引入 OTel SDK；真实基建阶段
可把 finished spans 导出到 OTLP。时钟/ID 可注入以便确定性测试。
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from pydantic import BaseModel


class SpanRecord(BaseModel):
    name: str
    trace_id: str
    span_id: str
    parent_id: str | None
    start_s: float
    duration_s: float
    attributes: dict[str, str]


@dataclass
class Span:
    name: str
    trace_id: str
    span_id: str
    parent_id: str | None
    start_s: float
    attributes: dict[str, str] = field(default_factory=dict)

    def set_attribute(self, key: str, value: str) -> None:
        self.attributes[key] = value


def _default_id_factory() -> Callable[[], str]:
    counter = 0

    def _next() -> str:
        nonlocal counter
        counter += 1
        return f"{counter:016x}"

    return _next


class Tracer:
    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.perf_counter,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._clock = clock
        self._id_factory = id_factory or _default_id_factory()
        self._stack: list[Span] = []
        self._finished: list[SpanRecord] = []

    @contextmanager
    def span(self, name: str, **attributes: str) -> Iterator[Span]:
        parent = self._stack[-1] if self._stack else None
        # 根 span 开新 trace；子 span 继承父的 trace_id。
        trace_id = parent.trace_id if parent is not None else self._id_factory()
        current = Span(
            name=name,
            trace_id=trace_id,
            span_id=self._id_factory(),
            parent_id=parent.span_id if parent is not None else None,
            start_s=self._clock(),
            attributes=dict(attributes),
        )
        self._stack.append(current)
        try:
            yield current
        finally:
            duration = self._clock() - current.start_s
            self._stack.pop()
            self._finished.append(
                SpanRecord(
                    name=current.name,
                    trace_id=current.trace_id,
                    span_id=current.span_id,
                    parent_id=current.parent_id,
                    start_s=current.start_s,
                    duration_s=duration,
                    attributes=dict(current.attributes),
                )
            )

    def finished(self) -> list[SpanRecord]:
        return list(self._finished)
