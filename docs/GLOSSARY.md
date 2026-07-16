# 术语表与数据字典（Glossary & Data Dictionary）

> 统一术语，避免人与代理对同一概念的理解漂移。随项目推进持续补充。

## A. 交易与量化术语

| 术语 | 含义 |
| --- | --- |
| Edge | 相对市场的可持续信息/执行优势，是盈利的来源假设。 |
| 基准（Benchmark） | 用于对比的被动策略：股票用 SPY 买入持有，加密用 BTC 买入持有。 |
| 超额收益（Alpha） | 扣成本后相对基准的收益。 |
| 回撤（Drawdown） | 从峰值到谷值的跌幅；最大回撤是风险硬约束之一。 |
| Sharpe / Sortino | 风险调整后收益指标；Sortino 只惩罚下行波动。 |
| Deflated Sharpe Ratio (DSR) | 对多重检验/回测次数做惩罚后的 Sharpe，抗过拟合。 |
| PBO | Probability of Backtest Overfitting，回测过拟合概率。 |
| Walk-forward | 滚动地"用过去训练、用紧邻未来验证"的时间序列验证法。 |
| Purged / Embargoed CV | 时间序列交叉验证中剔除信息泄漏的样本，防前视偏差。 |
| Look-ahead bias | 回测中误用了当时不可得的未来信息。 |
| Survivorship bias | 只用"存活标的"导致的乐观偏差。 |
| Point-in-time (PIT) | 只用"某时刻当时真实可得"的数据快照。 |
| 滑点（Slippage） | 预期成交价与实际成交价的差异。 |
| 换手率（Turnover） | 单位时间的交易量占比，直接影响成本。 |
| 仓位管理（Position sizing） | 决定每笔投入多少资金的方法（波动率目标、分数 Kelly 等）。 |
| Kill switch | 一键停止所有下单的全局熔断开关。 |
| Paper trading | 用真实行情但虚拟资金的模拟盘。 |
| Drift（live-vs-backtest） | 实盘/模拟盘表现与回测预期的偏离。 |

## B. AI / Agent 术语

| 术语 | 含义 |
| --- | --- |
| 构建期代理 | 在 Cursor 里写代码的 AI 编码代理。 |
| 运行时代理 | 系统内做信号提取的 LLM（本项目**不下单**）。 |
| 信号 / 因子（Signal / Factor） | LLM 从非结构化信息中提取的结构化数值/评分，供决策层使用。 |
| Eval（评测） | 独立衡量信号质量或策略表现的可复现测试。 |
| Spec-first | 先写规格再实现。 |
| ADR | Architecture Decision Record，架构决策记录。 |
| Prompt 版本化 | 固定并记录 prompt、模型版本、温度，以保证可复现。 |

## C. 数据字典（Data Dictionary）

> 在 M3 数据层建立时逐条填充：字段名、类型、来源、频率、PIT 说明、缺失值处理。

| 字段 | 类型 | 来源 | 频率 | PIT? | 备注 |
| --- | --- | --- | --- | --- | --- |
| `TODO` | | | | | |
