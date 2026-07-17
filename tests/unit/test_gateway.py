from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atrading.signals.budget import BudgetExceededError, CostBudget
from atrading.signals.gateway import AIGateway, GatewayError
from atrading.signals.llm_client import LLMResponse

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _Ok:
    def __init__(self, model: str = "ok", cost: float = 0.1) -> None:
        self.model = model
        self.cost = cost
        self.calls = 0

    def complete(self, *, system: str, user: str, temperature: float = 0.0) -> LLMResponse:
        self.calls += 1
        return LLMResponse(
            text="{}", model=self.model, input_tokens=1, output_tokens=1, cost_usd=self.cost
        )


class _Fail:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, *, system: str, user: str, temperature: float = 0.0) -> LLMResponse:
        self.calls += 1
        msg = "provider down"
        raise RuntimeError(msg)


def test_primary_success_records_budget() -> None:
    primary = _Ok(cost=0.2)
    budget = CostBudget(daily_limit_usd=1.0)
    gw = AIGateway(primary, budget=budget, now_fn=lambda: _NOW)
    resp = gw.complete(system="s", user="u")
    assert resp.model == "ok"
    assert budget.spent_total() == pytest.approx(0.2)


def test_falls_back_when_primary_fails() -> None:
    primary, fallback = _Fail(), _Ok(model="backup")
    gw = AIGateway(primary, [fallback], max_attempts=2, now_fn=lambda: _NOW)
    resp = gw.complete(system="s", user="u")
    assert resp.model == "backup"
    assert primary.calls == 2  # 重试 max_attempts 次后才降级
    assert fallback.calls == 1


def test_all_fail_raises_gateway_error() -> None:
    gw = AIGateway(_Fail(), [_Fail()], now_fn=lambda: _NOW)
    with pytest.raises(GatewayError):
        gw.complete(system="s", user="u")


def test_cache_avoids_second_call() -> None:
    primary = _Ok()
    gw = AIGateway(primary, enable_cache=True, now_fn=lambda: _NOW)
    gw.complete(system="s", user="u")
    gw.complete(system="s", user="u")  # 同输入 → 命中缓存
    assert primary.calls == 1


def test_budget_circuit_breaker() -> None:
    budget = CostBudget(daily_limit_usd=0.0)  # 无预算
    primary = _Ok()
    gw = AIGateway(primary, budget=budget, now_fn=lambda: _NOW)
    with pytest.raises(BudgetExceededError):
        gw.complete(system="s", user="u")
    assert primary.calls == 0  # 熔断：根本不发起真实调用
