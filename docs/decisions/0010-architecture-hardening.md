# ADR-0010：架构收敛与工程硬化（错误类型 / 配置化 / 时钟 / 组合根 / 追踪 / 持久化）

- 状态：Accepted
- 日期：2026-07-17
- 决策者：项目组（AI 代理执行）

## 背景（Context）

M1–M10 离线优先骨架（[ADR-0009](0009-offline-first-productionization.md)）跑通后，代码审查发现一批
**结构性缺口**：并非 bug，但影响一致性、安全可配置性、可观测性与可扩展性，且属于"越早修越便宜"
的地基类问题。本 ADR 记录这批一次性收敛。

## 决策（Decision）

| # | 缺口 | 处理 |
| --- | --- | --- |
| 1+10 | 风控限额硬编码；运行时配置未加载 | `core.RiskLimits` 上移 + `RiskLimits.from_yaml`；新增 `config.RunConfig`（加载 `configs/paper.yaml`：策略路径 / 日志 / **风控限额**）。限额纳入版本控制，不再散落代码 |
| 2 | `Clock` 协议定义却未用 | 新增 `clock.SystemClock`（真实钟）/`clock.ManualClock`（测试/回测钟）；`TradingLoop` 注入 `Clock`，新增 `tick()` 用注入钟跑一步 |
| 3 | 无领域错误类型，遍地 `except Exception` + 字符串 | 新增 `core.errors.AtradingError` 层次（Config/Data/Signal/Risk/Broker/Execution）；`GatewayError`/`BudgetExceededError` 并入 `SignalError`；配置/存储加载抛 `ConfigError`/`DataError` |
| 4 | 无组合根 / 策略注册表，组件到处手工拼装 | 新增 `registry`（名→策略工厂）+ `app.build_backtest` / `app.build_paper_loop` 组合根；CLI 新增 `atrading paper`（config 驱动装配完整闭环） |
| 5 | Broker 无订单生命周期，`RealisticBroker` 未接主循环 | `core.OrderStatus` 枚举；`Broker` 协议增 `advance(now)`；`SimulatedBroker` no-op、`RealisticBroker` 撮合推进；主循环 submit 后统一 `advance` → 高保真 broker 可直接替换进 loop |
| 7 | 持久化不统一、无多策略命名空间 | 新增 `SQLiteStateStore`（namespace 隔离 + upsert 事务 + 进程级并发安全），与 `FileStateStore` 同 `StateStore` 协议 |
| 8 | 可观测性未串联 | `TradingLoop` 注入 `Tracer`，observe/signals/decide/risk/execute/reconcile 各阶段 span；新增 `atrading_step_errors_total{error_type}`、`atrading_open_orders` 指标 |
| 9 | 信号无时效衰减 | `StrategyConfig.max_signal_age_days`；`RulesDecisionPolicy` 丢弃早于 `as_of - N 天` 的过期信号（防用陈旧信号交易） |
| 🟢 | 覆盖率未度量；PIT 无 schema 版本 | 引入 `pytest-cov`（CI `--cov-fail-under=85`，当前 92%）；`PITStore` 落盘 `_schema.json`，读端版本不兼容抛 `DataError`（预留迁移钩子） |

### 关于 #6（全异步事件循环）——**有意保留同步 + 时钟缝**

`TradingLoop` 保持**同步、单步 `step(now)`** 设计，不引入 asyncio 事件循环。理由：

- **决定论优先**：回测与实盘走同一同步决策代码，drift 只应来自真实摩擦（ADR-0003）。异步并发会引入非确定的时序，破坏可复现性与 golden 回归。
- **真实调度属真实基建**：实时多标的调度器 / 撮合并发 / 断线重连，需真实数据与网络，属 [ADR-0009](0009-offline-first-productionization.md) 中"收敛到人类开关"的真实基建阶段，离线无法有意义地验证。
- **已铺好接缝**：注入式 `Clock` + `tick()` 是未来实时调度器的对接点——调度器只需按节拍调用 `tick()`，决策/风控/执行代码零改动。

## 后果（Consequences）

- **正向**：安全关键参数（风控限额）配置化并纳入版本控制；组件装配收敛到组合根，新增策略=注册一个工厂；主循环可观测、可注入时钟、可换高保真 broker；持久化支持多策略。全量测试 197 → 223 全绿，覆盖率 92%。
- **代价 / 待办**：实时异步调度、真实券商订单状态机（NEW→PARTIALLY_FILLED→…）、跨进程并发存储仍待真实基建阶段；`SQLiteStateStore` 为单机方案，非分布式。
- **触发条件**：接入真实数据/券商时，以 `Clock`/`tick()` 缝挂实时调度器，以同协议真实 broker 替换 `RealisticBroker`。

## 关联

- 上游：[ADR-0009](0009-offline-first-productionization.md)、[ADR-0003](0003-backtest-live-parity.md)、[ADR-0006](0006-runtime-execution-and-safety.md)、[ADR-0004](0004-tech-stack.md)。
- 护栏：`.cursor/rules/10-trading-safety.mdc`、`20-research-rigor.mdc`。
