# ADR-0007：实验纪律与 regime/drift 监控方法

- 状态：Accepted
- 日期：2026-07-16
- 决策者：项目组（AI 代理执行）

## 背景（Context）

M6 要用系统化实验逼近成功指标，并**确认盈利是样本外可复现而非过拟合**，同时对抗
非平稳市场。核心风险：一次改多个变量说不清归因、偷偷试很多次挑最好看的、市场
regime 变了却不自知、模拟盘与回测悄悄分叉。参见 [M6 技术方案](../tech-specs/M6-experimentation-and-validation.md)、[EVAL-framework.md](../tech-specs/EVAL-framework.md)。

## 备选方案（Options）

- 实验归因：
  - A1 自由调参：快；但归因不清、极易过拟合。
  - A2 强制单变量 + 自动记账：慢一点；归因清晰、可累加 n_trials 惩罚过拟合。
- 多重检验惩罚：
  - B1 忽略试验次数：DSR/PBO 失去意义。
  - B2 `ExperimentRegistry` 自动累加 `n_trials` 喂给 DSR：量化"试很多次"的代价。
- Regime 检测方法：
  - C1 统计漂移（波动率比 + 平均相关性偏移）：简单、可解释、无需训练。
  - C2 变点检测 / 分布检验（CUSUM、KS、贝叶斯变点）：更灵敏；实现/调参复杂，易误报。
- OSS 对照基线：
  - D1 运行时依赖开源框架：真实；但重、需其 LLM/密钥、违背离线与红线。
  - D2 离线消费其**导出的权益曲线**作为第三类基线：轻、可复现、守混合红线。

## 决策（Decision）

- 实验选 **A2**：`ExperimentSpec` 用校验器**强制单变量**（overrides 恰好一个键且与
  `variable` 一致），结果带 `RunManifest`，可写入 `docs/experiments/` 形成证据链。
- 多重检验选 **B2**：`ExperimentRegistry.record/n_trials` 自动累加（可持久化 jsonl 跨会话），
  `n_trials` 喂入 `deflated_sharpe_ratio`——试验越多，同一 Sharpe 越不可信。
- Regime 选 **C1 统计漂移**作为一线告警（`RegimeMonitor`：vol_ratio + corr_shift 阈值），
  配 `RefreshPolicy`（alert / reduce_exposure / retire，且样本不足时只告警）。更灵敏的
  变点检测按需后续引入，不阻塞。
- OSS 基线选 **D2**：`oss_baseline_from_equity` 只消费开源框架导出的权益序列，离线、
  可复现、其 LLM 决策不接我们的执行（守 ADR-0001 混合红线）。
- drift 监控 `compute_drift`：对比模拟盘 vs 同期回测（同一 DecisionPolicy）的权重 L1 与
  收益差；"实盘=回测" → drift≈0；drift 大 = 成本被低估或代码分叉（违反 ADR-0003 须排查）。

## 后果（Consequences）

- 正面影响：归因清晰、过拟合有量化惩罚、regime/drift 有一线告警，go-live 记分卡可汇总。
- 负面影响 / 取舍：单变量实验迭代更慢；统计漂移检测较粗（可能漏检缓变或误报突变）；
  OSS 基线依赖外部导出数据的质量与同区间同标的口径。
- 后续需要注意 / 复核：`n_trials` 必须如实累加（含手动调参）否则 DSR 失真；regime 阈值需
  用历史数据校准；确定实验数量 N 与最终留出集时间窗（当前为开放项）。
