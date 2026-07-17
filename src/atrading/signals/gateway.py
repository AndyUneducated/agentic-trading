"""AI Gateway（M7）：在多个真实 LLMClient 前统一加路由/重试/降级/缓存/预算熔断。

实现 `LLMClient` 协议 → 对提取器透明（不改调用方）。设计要点：
- 供应商无关：primary + fallbacks 链，任一超时/报错自动降级到下一个。
- 预算熔断：调用前检查 CostBudget（耗尽即 BudgetExceededError，安全降级），调用后记账。
- 响应缓存：同 (system,user,temperature) 直接复用，省钱可复现。
仍是"只产信号，不下单"（ADR-0001）。
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from datetime import UTC, datetime

from atrading.signals.budget import CostBudget
from atrading.signals.llm_client import LLMClient, LLMResponse


class GatewayError(RuntimeError):
    """所有 provider（primary + fallbacks）均失败。"""


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


def _cache_key(system: str, user: str, temperature: float) -> str:
    payload = f"{temperature}|{system}|{user}"
    return hashlib.sha256(payload.encode()).hexdigest()


class AIGateway:
    def __init__(
        self,
        primary: LLMClient,
        fallbacks: Sequence[LLMClient] = (),
        *,
        budget: CostBudget | None = None,
        max_attempts: int = 2,
        enable_cache: bool = True,
        now_fn: Callable[[], datetime] = _utcnow,
    ) -> None:
        if max_attempts < 1:
            msg = "max_attempts 至少为 1"
            raise ValueError(msg)
        self._providers: list[LLMClient] = [primary, *fallbacks]
        self._budget = budget
        self._max_attempts = max_attempts
        self._cache: dict[str, LLMResponse] | None = {} if enable_cache else None
        self._now_fn = now_fn

    def complete(self, *, system: str, user: str, temperature: float = 0.0) -> LLMResponse:
        if self._cache is not None:
            cached = self._cache.get(_cache_key(system, user, temperature))
            if cached is not None:
                return cached

        # 预算熔断：耗尽即抛错，调用方安全降级（不继续真实调用）。
        if self._budget is not None:
            self._budget.check(now=self._now_fn())

        last_error: Exception | None = None
        for provider in self._providers:
            for _attempt in range(self._max_attempts):
                try:
                    response = provider.complete(system=system, user=user, temperature=temperature)
                except Exception as error:  # noqa: BLE001 — 网关须捕获任意 provider 故障并降级
                    last_error = error
                    continue
                if self._budget is not None:
                    self._budget.record(response.cost_usd, now=self._now_fn())
                if self._cache is not None:
                    self._cache[_cache_key(system, user, temperature)] = response
                return response
        msg = f"所有 provider 均失败（尝试 {len(self._providers)}×{self._max_attempts}）"
        raise GatewayError(msg) from last_error
