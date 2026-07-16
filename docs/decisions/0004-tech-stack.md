# ADR-0004：技术栈

- 状态：Accepted
- 日期：2026-07-16
- 决策者：项目所有者

## 背景（Context）

M1–M6 详细技术方案需要一个统一技术栈作为前提，否则各文档接口不一致。领域内成熟项目（FinRL、Qlib、TradingAgents、Nautilus、vectorbt）几乎全为 Python 生态。

## 决策（Decision）

- 语言：**Python 3.11+**。
- 包/环境：**uv**（备选 Poetry）。
- 类型化契约与配置：**Pydantic v2 + pydantic-settings**。
- 数据：pandas + pyarrow(parquet)（大规模可后续引 polars）。
- 回测引擎：**复用**（vectorbt / bt；回测-实盘一致场景评估 Nautilus），见 ADR-0002。
- LLM：供应商无关薄封装（OpenAI/Anthropic/DeepSeek/Ollama）。
- 券商：Alpaca（paper）+ CCXT（加密）。
- 测试：pytest（+ 可选 hypothesis）；结构化日志 structlog。
- 质量与 CI：ruff + mypy + GitHub Actions（lint/type/test/eval 门禁）。

## 后果（Consequences）

- 契约优先 + 类型化贯穿全项目，利于 AI 代理并行实现与 mock。
- 若 ADR-0002 最终选择"fork 某框架"，本栈可能需微调（如随框架的配置范式）。
- 版本与锁定文件纳入 git，保证可复现。
