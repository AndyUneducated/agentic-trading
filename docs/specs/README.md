# 规格（Specs）

规格先行（Spec-first）：任何模块实现前，先在此写清"做什么、输入输出契约、如何验证"，与人类对齐后再实现。

| 规格 | 内容 | 主要里程碑 |
| --- | --- | --- |
| [strategy-hypothesis.md](strategy-hypothesis.md) | Edge 假设、标的池、决策周期、动作空间、基准 | M2 |
| [llm-signal.md](llm-signal.md) | LLM 信号层的输入/输出 schema 契约与评测口径 | M2 / M4 |
| [backtest-eval.md](backtest-eval.md) | 数据层、回测引擎、过拟合防护、评测报告 | M3 |

约定：规格是"契约"，改动需同步更新受影响的评测与实验记录。
