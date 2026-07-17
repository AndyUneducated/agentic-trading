from __future__ import annotations

from collections.abc import Callable

from atrading.monitoring.tracing import Tracer


def _fake_clock() -> Callable[[], float]:
    ticks = iter([0.0, 0.5, 1.0, 2.0, 3.0, 4.0, 5.0])
    return lambda: next(ticks)


def test_span_records_duration() -> None:
    tracer = Tracer(clock=_fake_clock())
    with tracer.span("decide") as span:
        span.set_attribute("symbol", "AAPL")
    records = tracer.finished()
    assert len(records) == 1
    assert records[0].name == "decide"
    assert records[0].duration_s == 0.5
    assert records[0].attributes["symbol"] == "AAPL"


def test_nested_spans_share_trace_and_link_parent() -> None:
    tracer = Tracer(clock=_fake_clock())
    with tracer.span("loop_step"), tracer.span("extract"):
        pass
    records = {r.name: r for r in tracer.finished()}
    # 子 span 先结束 → 先入 finished
    child, parent = records["extract"], records["loop_step"]
    assert child.trace_id == parent.trace_id  # 同一 trace
    assert child.parent_id == parent.span_id  # 父子链接
    assert parent.parent_id is None  # 根 span


def test_separate_root_spans_get_new_traces() -> None:
    tracer = Tracer(clock=_fake_clock())
    with tracer.span("a"):
        pass
    with tracer.span("b"):
        pass
    records = tracer.finished()
    assert records[0].trace_id != records[1].trace_id
