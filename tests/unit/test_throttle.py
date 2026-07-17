from __future__ import annotations

from atrading.signals.throttle import PriorityThrottler, SignalRequest


def _req(symbol: str, priority: float, cost: float = 0.0) -> SignalRequest:
    return SignalRequest(symbol=symbol, priority=priority, est_cost_usd=cost)


def test_selects_top_priority_within_max() -> None:
    throttler = PriorityThrottler(max_requests=2)
    result = throttler.select([_req("A", 0.1), _req("B", 0.9), _req("C", 0.5)])
    assert [r.symbol for r in result.selected] == ["B", "C"]
    assert [r.symbol for r in result.paused] == ["A"]


def test_deterministic_tie_break_by_symbol() -> None:
    throttler = PriorityThrottler(max_requests=1)
    result = throttler.select([_req("Z", 0.5), _req("A", 0.5)])
    assert [r.symbol for r in result.selected] == ["A"]  # 同分按 symbol 升序


def test_budget_limits_selection() -> None:
    throttler = PriorityThrottler(max_requests=10, budget_left_usd=0.25)
    result = throttler.select([_req("A", 0.9, 0.2), _req("B", 0.8, 0.2)])
    assert [r.symbol for r in result.selected] == ["A"]  # 第二个超预算 → paused
    assert [r.symbol for r in result.paused] == ["B"]


def test_empty_candidates() -> None:
    result = PriorityThrottler(max_requests=5).select([])
    assert result.selected == []
    assert result.paused == []
