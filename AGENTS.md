# AGENTS.md — AI 代理工作手册

> 这是所有 AI 编码代理（构建期）在本仓库工作时的**首要上下文**。开始任何任务前先读本文件与 `.cursor/rules/`。人类协作者也应遵循。

## 1. 项目一句话

构建一个**混合架构**的 Agentic 交易系统：LLM 从非结构化信息中提取结构化信号/因子，硬规则 + 量化层负责决策与执行；目标是在严格验证下追求可持续盈利。标的为美股 / ETF / 加密货币，先模拟盘验证再考虑小额实盘。

## 2. 两层代理心智模型（本项目最重要的概念）

本项目存在两类"代理"，切勿混淆：

| | 构建期代理（Build-time） | 运行时代理（Runtime） |
| --- | --- | --- |
| 是谁 | 在 Cursor 里写代码的你（AI 编码代理） | 系统里做信号提取的 LLM |
| 产物 | 代码、文档、规格、评测 | 结构化信号/因子（**不下单**） |
| 治理方式 | 代码审查、测试、评测门槛 | Prompt 版本化、决策留痕、信号评测、运行时护栏 |

**运行时 LLM 只输出信号，绝不直接产生交易动作。** 决策与下单由确定性的规则/量化层完成。这是一条不可逾越的架构红线（见 `docs/decisions/0001-llm-positioning-hybrid.md`）。

## 3. 工作方式（AI-Native 工作流）

1. **规格先行（Spec-first）**：动手写实现前，确认 `docs/specs/` 里有对应规格；没有就先补规格并与人类对齐。
2. **评测即测试（Eval-driven）**：任何策略/信号/Prompt 改动，必须能被 `docs/specs/backtest-eval.md` 定义的评测或回测判定好坏。无评测不合并。
3. **单变量实验**：一次只改一个变量，结果写入 `docs/experiments/`（假设 → 设置 → 结果 → 结论）。
4. **决策留痕（ADR）**：有长期影响的技术/架构选择写入 `docs/decisions/`。
5. **小步提交**：小而聚焦的 PR，遵循 Conventional Commits。

## 4. 硬性禁令（Never do）

- 不得让运行时 LLM 直接下单或直接产生订单动作。
- 不得在未跑通评测/回测的情况下声称策略"有效"或"盈利"。
- 不得把密钥、API key、账户凭证写入代码或提交到 git（只用 `.env`，参照 `.env.example`）。
- 不得在回测中使用未来数据（look-ahead）或非 point-in-time 数据。
- 不得为让回测好看而反复调参却不做样本外验证（过拟合红线，见 `.cursor/rules/20-research-rigor.mdc`）。
- 未经明确人类批准，不得接入或操作任何**真实资金**账户；默认一切走模拟盘。

## 5. 关键文档地图

- 项目章程与成功标准：`docs/PROJECT_CHARTER.md`
- 系统架构与流程图：`docs/ARCHITECTURE.md`
- 里程碑与交付物：`docs/MILESTONES.md`
- 生产就绪度与差距：`docs/PRODUCTION-READINESS.md`
- 竞品/生产对标：`docs/LANDSCAPE.md`
- 详细技术方案：`docs/tech-specs/`（M1–M8 + EVAL）
- 术语与数据字典：`docs/GLOSSARY.md`
- 规格：`docs/specs/`（strategy-hypothesis / backtest-eval / llm-signal）
- 决策记录：`docs/decisions/`（ADR-0001 … 0008）
- 实验日志：`docs/experiments/`
- 持久规则：`.cursor/rules/`

## 6. Git 约定

- 分支：`main` 保护；特性分支 `feat/<scope>`、`fix/<scope>`、`docs/<scope>`、`exp/<name>`。
- 提交信息：Conventional Commits（`feat:`、`fix:`、`docs:`、`refactor:`、`test:`、`chore:`、`exp:`）。
- 每次提交尽量对应一个可验证的小改动。

## 7. 当前阶段

**M0–M6 + EVAL 已落地（离线优先，125 测试全绿）**：契约 → PIT 数据 + 回测 → 防过拟合评测 → LLM 信号层（离线 stub）→ 决策 + 预交易风控门 + 模拟盘闭环 → 实验框架 + regime/drift 监控。代码在 `src/atrading/`。

**下一步：生产化路线 M7–M10**（见 `docs/MILESTONES.md` 与 `docs/PRODUCTION-READINESS.md`）：M7 真实接入（数据+LLM）→ M8 生产执行引擎（采用 Nautilus）→ M9 可观测性/运维 → M10 合规 + 小额实盘。排序依据 `docs/decisions/0008-production-roadmap-and-oss-adoption.md`（**先真实 alpha 证据，后重工程**）。
