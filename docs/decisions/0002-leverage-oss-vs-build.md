# ADR-0002：复用成熟开源引擎 vs 自建

- 状态：Accepted
- 日期：2026-07-16
- 决策者：项目所有者

## 背景（Context）

存在大量成熟开源项目（见 [../LANDSCAPE.md](../LANDSCAPE.md)）：回测引擎（bt、vectorbt、Qlib）、生产级执行（Nautilus Trader、QuantConnect Lean）、端到端 AI 交易（FinRL-X）、多智能体 LLM（TradingAgents、ai-hedge-fund）。从零手搓这些组件成本高且易出错（尤其回测引擎的未来函数/成本建模）。项目目标是**盈利**而非造框架。

## 备选方案（Options）

- **A 全自建**：完全从零。优点：完全掌控、学习充分。缺点：慢、易犯已知错误、重复造轮子。
- **B 复用引擎 + 自建策略/信号层**：回测/执行复用成熟库，专注在自己的信号与策略 Edge 上。优点：快、可靠、把精力放在真正差异化处。缺点：需理解并适配第三方接口。
- **C 直接 fork 某个框架**（如 FinRL-X / TradingAgents）二次开发。优点：起步最快。缺点：受其架构约束，混合架构红线可能需要改造。

## 决策（Decision）

选择 **B**：回测复用 bt/vectorbt（藏在我们自己的统一决策接口后），执行参考 Nautilus 模式或用 Alpaca SDK，把自研聚焦在 **LLM 信号层与规则决策层**；同时把 TradingAgents / ai-hedge-fund / FinRL 作为 **对照基准**而非运行时依赖。

## 后果（Consequences）

- 若选 B/C：需在 M3 评估所选引擎是否满足我们的过拟合防护与统一决策接口要求（ADR-0003）。
- 复用不等于放松严谨性：第三方引擎的成本模型/PIT 处理仍需按 `20-research-rigor` 校验。
- 保持混合红线：任何被复用的多智能体框架都不得让 LLM 直接下单。
