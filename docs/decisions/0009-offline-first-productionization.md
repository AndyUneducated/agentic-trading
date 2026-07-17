# ADR-0009：M7–M10 离线优先落地（同协议骨架，延迟重依赖与真实联网）

- 状态：Accepted
- 日期：2026-07-16
- 决策者：项目组（AI 代理执行）

## 背景（Context）

[ADR-0008](0008-production-roadmap-and-oss-adoption.md) 已确定生产化顺序 M7 → M8 →（并行 M9）→ M10。执行时面临两条硬约束：

- **本机算力有限**，且明确要求"尽量避免真实 LLM 调用"。
- 研究纪律与安全护栏：默认 `TRADING_MODE=paper`；密钥不入库；**无真实 alpha 证据不重工程**；未经人类批准不碰真钱。

问题：在不引入重依赖、不做真实网络/资金调用的前提下，如何让 M7–M10 **真正可落地、可测试、可评测**，而不只是写文档占位？

## 备选方案（Options）

- **D1 全量真实接入**：直接引入 `nautilus_trader` + 真实 LLM/券商 SDK，联网跑通。
- **D2 纯文档占位**：只写 tech-spec，不落代码，等有算力/预算再实现。
- **D3 离线优先骨架（本 ADR）**：实现**全部离线可测的结构**，把真实网络/重依赖/资金收敛到明确的"人类开关"后，且新组件**实现现有 `core` Protocol**，真实实现日后可零改替换。

## 决策（Decision）

选 **D3**，四个里程碑均落"离线优先骨架 + 同协议可替换"：

| 里程碑 | 离线已落地 | 收敛到人类开关（未做） |
| --- | --- | --- |
| **M7 真实接入** | `AIGateway`（重试/降级/缓存/预算熔断）、`CostBudget`、`PriorityThrottler`、`InMemoryNewsSource`(PIT)、`OpenAICompatibleClient` 结构 | 真实 LLM 联网调用、真实信号样本外实验 |
| **M8 执行真实性** | `CommissionModel`/`SlippageModel`、`RealisticBroker`（延迟/部分成交/费用/滑点）、回测-实盘 parity | 采用 Nautilus（Rust 重依赖）、真实 paper 券商 |
| **M9 可观测性** | `MetricsRegistry`(Prometheus 文本)、埋点、`AlertRule`、`Tracer`、Dockerfile、runbook | Grafana/Alertmanager/OTLP、密钥托管、断连演练 |
| **M10 合规上线** | `GoLiveGate`(三重红线)、`CapitalRampController`(放量/回滚)、`AuditTrail`(哈希链) | 合规对接、真实小额实盘签署放量 |

关键原则：

1. **同协议可替换**：新组件实现现有 `LLMClient` / `core.Broker` / `DataSource` / `SignalSource` Protocol。真实后端（LLM/Nautilus/券商）接入时，提取器 / 决策 / loop **零改动**。
2. **真实成本与摩擦显式建模**：`RealisticBroker` 与 `SimulatedBroker` 同协议，无摩擦下 parity 一致，加摩擦后 drift 完全归因于显式成本（对齐 ADR-0003）。
3. **安全红线代码化**：`GoLiveGate` 要求记分卡全绿 + **人类明确批准**（缺省 False）+ KILL_SWITCH 关闭；`CapitalRampController` 硬止损自动停机。LLM 仍绝不下单。
4. **避免烧钱/联网**：真实网络路径（`OpenAICompatibleClient.complete`）不在 CI 执行；无重依赖引入。

## 后果（Consequences）

- **正向**：M7–M10 均有可运行、可测试、可评测的实体（新增单测使全量套件从 137 → 189 全绿），而非纸面；真实基建接入路径清晰且低改动风险；严守算力/预算/安全约束。
- **代价 / 待办**：真实 alpha 证据、执行保真度校准、真实运维演练、合规与实盘签署仍**待真实基建阶段**完成——这些依赖真实数据/网络/人类闸门，不可离线证明。
- **触发条件**：当获得算力/预算与人类批准后，按上表"人类开关"逐项接入，届时各 tech-spec 的 Exit Gate 才算真正闭合。

## 关联

- 上游：[ADR-0008](0008-production-roadmap-and-oss-adoption.md)（顺序与 OSS 采用）、[ADR-0003](0003-backtest-live-parity.md)（回测-实盘同源）、[ADR-0001](0001-llm-positioning-hybrid.md)（LLM 不下单）。
- 规格：`tech-specs/M7–M10` 各含"实现状态"小节。
- 护栏：`.cursor/rules/10-trading-safety.mdc`、`20-research-rigor.mdc`。
