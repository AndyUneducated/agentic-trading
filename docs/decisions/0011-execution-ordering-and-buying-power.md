# ADR-0011：执行排序与买力约束（卖单优先 + 买单缩量）

- 状态：Accepted
- 日期：2026-07-17
- 决策者：项目组（AI 代理执行）

## 背景（Context）

把 `agentic-trading` 的 `TradingLoop` 接入 [`paper-trading-platform`](../../../paper-trading-platform)（PTP，会**校验买力**的模拟券商）做端到端验证时，复杂多标的再平衡 Demo 每轮 88–95 单中有 **19–23 单**被拒，拒因 100% 为 `insufficient_buying_power`，成交率仅 ~76%。

根因有二：

1. **买卖单混排**：`weights_to_orders` 按标的字母序生成订单，再平衡时买单可能先于卖单提交；对校验买力的券商，卖单回款未到账 → 买单被拒。
2. **满仓无缓冲**：策略目标常为满仓（gross=1.0），留存现金≈0；末笔买单因成交价/量子取整漂移超出可用现金几分钱 → 被拒。

我方 `SimulatedBroker`/`RealisticBroker` **不校验买力**（允许现金为负），长期**掩盖**了该缺陷；PTP 的复式记账 + 买力校验才暴露它。

## 决策（Decision）

在**订单生成层**（`weights_to_orders`，正确的责任边界——"不发下不起的单"）修复：

1. **卖单优先**：返回列表中所有 `sell` 排在 `buy` 之前；再平衡先卖出释放现金再买入。gross ≤ 1 时可保证买单资金充足。
2. **买力约束**：买单累计名义 ≤ **可用买力 = 当前现金 + 卖单回款**，并预留 `cash_buffer`（默认 0.5%）吸收成交/量子取整漂移；超出时对末笔买单**缩量**（部分再平衡），再不足则跳过。

不改动 `SimulatedBroker`/`RealisticBroker` 的宽松语义（避免破坏既有 parity/回归测试并扩大范围）；**执行真实性的买力校验由 PTP 承担**，并把"PTP 集成 Demo 零拒单"确立为验收信号。

## 备选方案（Options）

- **A（选定）订单生成层修复**：卖单优先 + 买力缩量。责任边界正确、对所有下游券商通用、决定论、不改 broker 语义。
- **B broker 层强制买力**：给 AT 的 broker 加买力校验。能在 AT 单测内复现，但改变既有 broker 契约、风险波及 parity 测试、且治标不治本（策略仍在发不起的单）。
- **C 提高风控门**：在 `PreTradeRiskGate` 加买力检查。但风控在**提交前**用步初现金判断，会误拒"卖出后本可负担"的买单（时序错位）。

## 后果（Consequences）

- **正向**：PTP 复杂 Demo 拒单 19/23/21 → **0/0/0**，成交率 100%；再平衡对任何校验买力的真实/模拟券商稳健；决定论不变（`client_order_id` 仍确定性）。回归由 `test_order_gen`（卖单优先 + 买力上限）与 `test_buying_power`（fake 校验买力 broker 跑满仓再平衡零拒单）锁死，全量 223 → 226 全绿。
- **代价 / 待办**：`cash_buffer` 为固定默认（0.5%），未按标的波动/费用自适应；未建模融资/做空保证金与 T+N 结算资金（见 [PAPER-TRADING-INTEGRATION.md](../PAPER-TRADING-INTEGRATION.md) 差距矩阵 P1）；AT 侧 broker 仍不校验买力（P4，靠 PTP 集成兜底）。

## 关联

- 集成规格与差距矩阵：[PAPER-TRADING-INTEGRATION.md](../PAPER-TRADING-INTEGRATION.md)。
- 上游：[ADR-0010](0010-architecture-hardening.md)（`advance` 契约）、[ADR-0003](0003-backtest-live-parity.md)（回测-实盘一致：drift 只应来自真实摩擦，买力约束即真实摩擦）、[ADR-0006](0006-runtime-execution-and-safety.md)（执行与风控）。
