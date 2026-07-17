# Incident Playbook（事故处置手册）

> M9 运维交付物。原则：**异常默认安全降级（不交易）** 而非盲目下单；一切操作留痕。真实告警/密钥托管随 M7/M8 真实接入补齐；本手册先固化处置流程。

## 0. 快速动作

| 场景 | 立即动作 |
| --- | --- |
| 任何失控/不确定 | 置 `KILL_SWITCH=true` → 所有订单被 `PreTradeRiskGate` 拒绝 |
| 需要停机 | 优雅停机：收尾持久化 `EngineState`；重启后自动对账恢复 |
| 疑似实盘异常 | 切回 `TRADING_MODE=paper`（`live_confirmed=false`） |

## 1. 关键指标与告警映射（来自 `/metrics`）

| 指标 | 异常信号 | 告警 → 处置 |
| --- | --- | --- |
| `atrading_steps_total{result="degraded"}` | 升高 | §2 数据/依赖异常 |
| `atrading_risk_denials_total{reason}` | 突增 / kill 触发 | §3 护栏 |
| `atrading_reconcile_mismatch` | `> 0` | §4 对账 |
| `atrading_llm_cost_usd_total` | 超日/月预算 | §5 成本 |
| （M7）feed/券商心跳 | 超时 | §6 断连 |

## 2. 数据源 / 依赖异常

1. 确认 `degraded` 步的 `error`（结构化日志）。
2. 系统已自动安全降级（该步不交易）——**无需紧急下单**。
3. 切备用数据源 / 修复后，下一循环自然恢复；必要时手动触发对账。

## 3. 护栏触发（风控拒单 / kill switch）

1. 区分：正常拒单（越限，符合预期）vs 误触发。
2. 若误触发：复核 `RiskLimits` 与价格输入，修正后放行；变更留痕。
3. kill switch 被激活：确认原因，人工评估后再解除。

## 4. 对账不一致（`reconcile_mismatch > 0`）

1. 查 `ReconcileReport`：`unexpected_fills`（幽灵成交）/ `position_mismatches`（持仓漂移）。
2. 以券商为准核对 `client_order_id`；补记漏单 / 排查重复。
3. 未查清前置 `KILL_SWITCH=true`，避免在错误状态上继续交易。

## 5. LLM 成本失控

1. AI gateway（M7）触发预算熔断 → 停止真实调用。
2. 降级：切便宜/本地模型（DeepSeek/Ollama），或暂停信号（标注 "AI paused"）。
3. Hot Path 不依赖新信号仍可安全运行（用既有持仓/规则）。

## 6. 券商断连（M7/M8）

1. 停止提交新单；退避重连。
2. 重连后**先对账**（补齐成交/持仓）再恢复交易。
3. 幂等 `client_order_id` 保证重放不重复下单。

## 7. 崩溃恢复

1. 进程重启 → `FileStateStore.load()` 恢复 `EngineState`。
2. 启动即对账，校验持仓/现金/未平仓一致。
3. 幂等保证：已提交订单不重复。

## 8. 演练（Drills）

- 定期演练：数据中断、券商断连、崩溃重启、成本熔断（记录 RTO/结果）。
- 演练脚本化后纳入 CI/CD 前的发布检查（M9 准出）。
