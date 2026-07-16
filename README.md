# Agentic Trading

一个以 AI 参与决策的量化交易研究项目，目标是在严格的回测与模拟盘验证下追求可持续盈利。

- **标的范围**：美股、ETF、加密货币（先聚焦少量高流动性标的）
- **AI 定位（混合架构）**：LLM 负责从非结构化信息（新闻/财报/公告/情绪）中提取**结构化信号/因子**；**硬规则 + 量化层**负责决策与下单。LLM 不直接触碰交易动作。详见 [docs/decisions/0001-llm-positioning-hybrid.md](docs/decisions/0001-llm-positioning-hybrid.md)。
- **资金策略**：回测 → 模拟盘验证 → 达标后小额实盘 → 逐步放量。
- **当前状态**：规划中（Planning）。尚未接入任何实盘资金。

> 免责声明：本项目仅用于个人研究，不构成任何投资建议。加密货币与股票交易存在本金损失风险。

## 从这里开始阅读

| 文档 | 作用 |
| --- | --- |
| [AGENTS.md](AGENTS.md) | 给 AI 编码代理的顶层上下文与工作约定（**最先读**） |
| [docs/PROJECT_CHARTER.md](docs/PROJECT_CHARTER.md) | 项目章程：成功/失败标准、边界、约束 |
| [docs/MILESTONES.md](docs/MILESTONES.md) | 阶段与里程碑，及每个里程碑的明确交付物 |
| [docs/LANDSCAPE.md](docs/LANDSCAPE.md) | 竞品与生产实践对标、差距分析与取舍 |
| [docs/tech-specs/](docs/tech-specs/) | M1–M6 + Eval 的详细技术方案（面向 AI-coding） |
| [docs/GLOSSARY.md](docs/GLOSSARY.md) | 交易术语与数据字典 |
| [docs/specs/](docs/specs/) | 各模块规格（strategy / backtest-eval / llm-signal） |
| [docs/decisions/](docs/decisions/) | 架构决策记录（ADR） |
| [docs/experiments/](docs/experiments/) | 实验日志 |

## 目录约定

```text
.
├── AGENTS.md              # AI 代理上下文
├── .cursor/rules/         # Cursor 持久化规则（安全/严谨性/工作流）
├── docs/                  # 规格、决策、术语、里程碑、实验
├── .env.example           # 环境变量样例（密钥永不入库）
└── README.md
```

工程代码目录（`src/` 等）将在里程碑 M3 之后引入，本阶段先沉淀规格与流程。
