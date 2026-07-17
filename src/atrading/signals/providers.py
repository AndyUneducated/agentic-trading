"""真实 LLM 后端适配（M7）：OpenAI 兼容 Chat Completions。

同一个类覆盖 OpenAI / DeepSeek / 本地 Ollama（均兼容 /chat/completions），仅 base_url、
model、单价不同。实现 `LLMClient` 协议 → 对提取器/网关透明。

约束（本机算力有限 + 避免真实调用）：
- 仅用标准库 `urllib`，不引入重依赖。
- `complete()` 会发起网络请求，**不在 CI 中执行**（无 key/网络）；成本敏感优先便宜后端。
- 密钥仅由调用方从 `Settings`/密钥托管注入，绝不写入代码。
红线：只产文本/信号，不下单（ADR-0001）。
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any

from atrading.signals.llm_client import LLMResponse


class OpenAICompatibleClient:
    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        usd_per_1k_input: float = 0.0,
        usd_per_1k_output: float = 0.0,
        timeout: float = 30.0,
    ) -> None:
        self._model = model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._price_in = usd_per_1k_input
        self._price_out = usd_per_1k_output
        self._timeout = timeout

    def complete(  # pragma: no cover - 真实网络调用，不在离线 CI 执行
        self, *, system: str, user: str, temperature: float = 0.0
    ) -> LLMResponse:
        body = json.dumps(
            {
                "model": self._model,
                "temperature": temperature,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            }
        ).encode("utf-8")
        request = urllib.request.Request(  # noqa: S310 — 固定 https 服务端点
            f"{self._base_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self._timeout) as resp:  # noqa: S310
            payload: dict[str, Any] = json.loads(resp.read().decode("utf-8"))

        text = str(payload["choices"][0]["message"]["content"])
        usage: dict[str, Any] = payload.get("usage") or {}
        input_tokens = int(usage.get("prompt_tokens", 0))
        output_tokens = int(usage.get("completion_tokens", 0))
        cost = round(
            input_tokens / 1000.0 * self._price_in + output_tokens / 1000.0 * self._price_out,
            6,
        )
        return LLMResponse(
            text=text,
            model=self._model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
        )


def deepseek_client(
    *, api_key: str, model: str = "deepseek-chat", **kwargs: float
) -> OpenAICompatibleClient:
    """成本敏感优先后端（价格约为 GPT 级的 1/10 量级）。"""
    return OpenAICompatibleClient(
        model=model, api_key=api_key, base_url="https://api.deepseek.com/v1", **kwargs
    )


def ollama_client(
    *, model: str, base_url: str = "http://localhost:11434/v1"
) -> OpenAICompatibleClient:
    """本地零 API 成本后端（需本机已运行 Ollama）。"""
    return OpenAICompatibleClient(model=model, api_key="ollama", base_url=base_url)
