# ADR-0005：评测框架与防过拟合门禁

- 状态：Accepted
- 日期：2026-07-16
- 决策者：项目组（AI 代理执行）

## 背景（Context）

交易系统的最大风险不是 bug，而是**把回测调得好看**（过拟合）与**运气冒充 Edge**。
需要一套"测试套件"级别的评测框架，作为约束两层不确定性的锚点，且必须**结构性地**
防止在全样本上反复调参、偷看最终验证集、忽略多重检验。参见 [EVAL-framework.md](../tech-specs/EVAL-framework.md)。

## 备选方案（Options）

- 方案 A：只算收益/夏普等基础指标，人工判断是否过拟合。
  - 优点：简单快。缺点：无结构性约束，极易自欺；不可复现的"看着不错"。
- 方案 B：把防过拟合做成不可绕过的 API（强制切分 + HoldoutGuard + DSR/PBO + 多基线 + 记分卡）。
  - 优点：过拟合防护写进代码与流程，可测、可复现、可审计。缺点：前期投入大。
- 方案 C：直接依赖第三方回测平台的评测。
  - 优点：省事。缺点：口径不透明、与我们的 PIT/成本/决策接口不一致，难做统一门禁。

## 决策（Decision）

选 **方案 B**。在 `src/atrading/eval/` 建立分层评测框架：

- `metrics.py`：纯函数指标（收益/回撤/Sharpe/Sortino/换手/超额），可手算校验。
- `validation.py`：`walk_forward` / `purged_kfold`（含 embargo）/ `HoldoutGuard`（最终留出集访问留痕、默认禁止反复访问）。
- `overfit.py`：`deflated_sharpe_ratio`（用 `n_trials` 惩罚多重检验）、`pbo`。
- `baselines.py`：zero / price_only / buy_hold 经**同一引擎同一成本**运行，保证可比。
- `signal_eval.py`：IC / rank-IC / 命中率 / 显著性（M4 已落地）。
- `scorecard.py`：`CharterThresholds`（成功指标单一数据源）+ `build_edge_criteria` + `GoLiveScorecard`（全绿才放行）。
- `report.py`：一键 markdown 报告（纯文本、易 diff、CI artifact 友好）。

关键约束：
1. **最终留出集只能经 `HoldoutGuard` 访问**，且默认一次性（防偷看后调参）。
2. **`n_trials` 由实验框架(M6)自动累加**喂入 DSR，量化"偷偷试很多次"的惩罚。
3. **阈值集中在 `CharterThresholds`**，不散落在各处；具体数值以 CHARTER/M0 定稿为准，当前为行业惯例默认值（回撤<20%、Sharpe>1.0、超额>0、DSR>0.95、PBO<0.5）。
4. **报告选 markdown 而非 HTML**：无额外依赖、可复现、便于版本 diff。

## 后果（Consequences）

- 正面影响：过拟合防护从"自觉"变"强制"；评测可复现、可进 CI 门禁（`无评测不合并`）。
- 负面影响 / 取舍：DSR/PBO 为学术近似（Bailey & López de Prado），参数（skew/kurtosis/n_trials）质量决定其价值；report 为 markdown，交互性弱于 HTML。
- 后续需要注意 / 复核：CHARTER 阈值 M0 定稿后需覆盖默认值；`n_trials` 必须由 M6 registry 如实累加，否则 DSR 失去意义；OSS 基线（第三类）在 M6 接入。
