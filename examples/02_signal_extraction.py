"""示例 02：LLM 信号抽取（AI 网关 + 预算熔断 + 缓存，全离线）。

真实后端只需把 KeywordLLMClient 换成 OpenAICompatibleClient，其余不变。

    uv run python examples/02_signal_extraction.py
"""

from __future__ import annotations

from datetime import UTC, datetime

from atrading.signals import (
    AIGateway,
    CostBudget,
    Document,
    InMemoryNewsSource,
    KeywordLLMClient,
    SentimentExtractor,
    SignalCache,
    load_prompt,
)


def main() -> None:
    budget = CostBudget(daily_limit_usd=5.0)  # 预算耗尽即熔断（安全降级）
    gateway = AIGateway(KeywordLLMClient(), budget=budget)  # 多后端重试/降级/缓存
    extractor = SentimentExtractor(
        gateway,
        load_prompt("sentiment", "v1", expected_schema="SignalDraft"),
        cache=SignalCache(),  # 指纹去重：同输入不重复调用
    )

    news = InMemoryNewsSource(
        [
            Document(
                source_id="wire",
                symbol="AAPL",
                published_at=datetime(2026, 1, 2, tzinfo=UTC),
                text="Apple beats earnings, raises guidance; record revenue.",
            ),
        ]
    )
    as_of = datetime(2026, 1, 3, tzinfo=UTC)
    docs = news.documents_as_of(as_of, ["AAPL"])  # PIT：只见已发布文档
    result = extractor.extract(symbol="AAPL", as_of=as_of, documents=docs)

    print(f"情绪 {result.signal.sentiment:+.2f} | 置信 {result.signal.confidence:.2f}")
    print(f"成本 ${result.cost_usd:.4f} | 缓存命中 {result.cache_hit}")


if __name__ == "__main__":
    main()
