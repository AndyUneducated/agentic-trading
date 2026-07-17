"""M7 端到端（离线）：新闻源(PIT) → AIGateway → 提取器 → 信号质量 eval。

用离线 KeywordLLMClient 作网关后端（零真实调用），验证 M7 结构就位后，提取出的
信号能被信号级 eval 直接判定（IC/显著性）——真实后端接入后同一 harness 即可评判
"信号是否优于价量基线"。
"""

from __future__ import annotations

from datetime import UTC, datetime

from atrading.eval.signal_eval import evaluate_signal
from atrading.signals import (
    AIGateway,
    Document,
    InMemoryNewsSource,
    KeywordLLMClient,
    SentimentExtractor,
    load_prompt,
)

_POS = "beat strong surge record profit growth rally"
_NEG = "miss weak plunge loss fraud lawsuit bankruptcy"


def _doc(symbol: str, text: str) -> Document:
    return Document(
        source_id="news",
        symbol=symbol,
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
        text=text,
    )


def test_gateway_pipeline_feeds_signal_eval() -> None:
    # 5 个标的：正/负面文档交替，未来收益与情绪同号 → IC 应为正。
    setup = [
        ("S0", _POS, 0.03),
        ("S1", _NEG, -0.02),
        ("S2", _POS, 0.04),
        ("S3", _NEG, -0.05),
        ("S4", _POS, 0.01),
    ]
    news = InMemoryNewsSource([_doc(sym, text) for sym, text, _ in setup])
    gateway = AIGateway(KeywordLLMClient())
    prompt = load_prompt("sentiment", "v1", expected_schema="SignalDraft")
    extractor = SentimentExtractor(gateway, prompt)

    as_of = datetime(2026, 1, 2, tzinfo=UTC)
    sentiments: list[float] = []
    forward_returns: list[float] = []
    for symbol, _text, fwd in setup:
        docs = news.documents_as_of(as_of, [symbol])
        result = extractor.extract(symbol=symbol, as_of=as_of, documents=docs)
        sentiments.append(result.signal.sentiment)
        forward_returns.append(fwd)

    evaluation = evaluate_signal(sentiments, forward_returns)
    assert evaluation.n == 5
    assert evaluation.ic > 0.5  # 情绪与未来收益强正相关（离线构造）
    assert evaluation.hit_rate >= 0.8  # 方向命中率高
