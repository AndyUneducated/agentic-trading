# ADR-0006：运行时执行架构与安全护栏

- 状态：Accepted
- 日期：2026-07-16
- 决策者：项目组（AI 代理执行）

## 背景（Context）

M5 要跑通 observe → 信号 → 决策 → 风控 → 执行 → 对账 → 持久化 的闭环，且必须满足
交易系统的硬性安全要求：**任何订单不得绕过风控**、进程崩溃可安全恢复不重复下单、
内部状态与券商状态可对账。同时本机算力受限、且不接真实资金——需要一个可离线、
确定性、可测试的运行时。参见 [M5 技术方案](../tech-specs/M5-decision-execution-paper.md)、
`.cursor/rules/10-trading-safety.mdc`。

## 备选方案（Options）

- 执行券商：
  - A1 直接对接 Alpaca paper / CCXT testnet：真实感强；但需密钥/联网，测试不确定、CI 不可复现。
  - A2 进程内 `SimulatedBroker`（即时按价成交、按 client_order_id 去重）：离线、确定、可测；不覆盖真实撮合/延迟。
- 状态持久化：
  - B1 文件式 JSON（原子写 tmp+os.replace）：零依赖、可读、易备份；高频下 IO 较慢。
  - B2 SQLite / Redis：更强并发/查询；引入依赖与运维。
- 风控位置：
  - C1 风控前置为独立门（execution 只接受 approved）：无旁路、可断言。
  - C2 在下单函数内散点校验：易遗漏、难测"无旁路"。

## 决策（Decision）

- 券商选 **A2 `SimulatedBroker`**（离线、确定、幂等去重）作为当前实现，藏在 `core.Broker`
  协议后；真实 Alpaca/CCXT 适配后续按同一协议替换，不改动决策/循环/风控。
- 状态选 **B1 文件式 JSON + 原子写**，`EngineState` 为持久化契约，设计为 crash-only：
  任意时刻被杀，重启 `load()` + 启动对账 + 幂等 `client_order_id` → 不重复/不丢单。
- 风控选 **C1 独立前置门 `PreTradeRiskGate`**：全局闸门（kill switch / 交易模式 / 日亏熔断）
  一票否决；逐单闸门（单笔名义 / 单标的名义 / 总敞口 / 下单频率）。`TradingLoop`
  **只提交 `RiskDecision.approved`**，并有"无旁路"测试覆盖。
- 决策层 `RulesDecisionPolicy` 实现统一 `DecisionPolicy`，与回测**同一实现**（ADR-0003），
  并有"回测-实盘目标权重一致"的 parity 测试。
- 主循环 `TradingLoop.step` 全程 try/except **安全降级**：任一步异常则本步不交易、记录，
  进入下一循环，绝不整体崩溃。

## 后果（Consequences）

- 正面影响：闭环可离线、确定、可测；安全属性（无旁路 / 幂等恢复 / 对账）有断言保护。
- 负面影响 / 取舍：`SimulatedBroker` 即时成交、无滑点/延迟/部分成交，真实性有限；文件式
  状态不适合高频/多进程；真实券商接入前，drift 只能与回测对比而非真实实盘。
- 后续需要注意 / 复核：接真实 paper 券商时补充延迟/部分成交/拒单处理；评估 SQLite/Redis；
  确定对账周期与不一致熔断阈值；连续运行天数 N（Exit Gate）需在真实 paper 环境验证。
