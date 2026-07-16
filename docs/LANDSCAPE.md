# 竞品与生产实践对标（Landscape & Gap Analysis）

> 调研日期：2026-07。目的：对照开源同类项目与生产级系统，找出差距并决定"抄什么、避什么、补什么"。站在巨人肩膀上，而非重复造轮子。

## 1. 对标对象一览

| 项目 | 定位 | 关键特征 | 对我们的启发 |
| --- | --- | --- | --- |
| [TradingAgents](https://github.com/TauricResearch/TradingAgents)（~9万星） | 多智能体 LLM 模拟交易公司 | LangGraph 编排；分析师/研究员(多空辩论)/交易员/风控分层；决策留痕 + 断点续跑；多 LLM 供应商 | 多视角"辩论"提升可解释性、降低单模型偏差；但**明确声明不作投资建议、不建议实盘** |
| [ai-hedge-fund](https://github.com/virattt/ai-hedge-fund)（~6万星） | 投资人人格多智能体 | 14 位投资大师人格 + 估值/情绪/基本面/技术/风险分析师；含回测器；**不下单** | 人格化=可解释、便于对论点做压力测试；数据依赖公开信息 |
| [FinRL / FinRL-X](https://github.com/AI4Finance-Foundation/FinRL) | RL + AI-native 生产级基础设施 | 权重为中心的统一接口（回测↔实盘一致）；**bt 引擎显式建模交易成本**；Alpaca 多账户；**订单/组合/策略三级风控**；多源数据自动回退 + SQLite 缓存；Pydantic 类型化配置 | 生产级模块化范式的最佳参考；回测-实盘一致性、三级风控值得直接借鉴 |
| [Microsoft Qlib](https://github.com/microsoft/qlib) | AI 量化研究平台 | 全 ML 管线：数据→建模→回测；alpha 挖掘、风险建模、组合优化、订单执行；RD-Agent 自动化研发 | 成熟的研究工作流与数据服务器设计 |
| [Nautilus Trader](https://nautilustrader.io) | 生产级交易系统 | **崩溃恢复**(状态持久化/重启对齐)；**LiveExecutionEngine 对账**(与交易所状态对齐)；**预交易 RiskEngine**(仓位/名义/下单频率校验→OrderDenied)；单线程确定性事件序；回测-实盘同一套代码 | 生产执行工程的教科书：对账、预交易风控门、崩溃恢复、回测-实盘一致 |
| QuantConnect Lean | 券商集成的端到端平台 | 托管基础设施；实盘 vs 样本外回测的偏离监控 | live-vs-backtest 偏离监控作为一等公民 |

## 2. 我们相对领先/持平的地方

我们的计划在**研究严谨性**上已达到或超过多数开源项目（很多开源项目恰恰在这块偷懒）：
- 防过拟合：walk-forward、purged/embargoed CV、最终验证集、DSR/PBO（多数开源项目没有）。
- Point-in-time 数据 + 防幸存者偏差 + 真实成本建模（FinRL-X 才明确做成本，很多框架默认零成本）。
- 混合架构红线：LLM 不下单（比"让 LLM 自主交易"更稳，符合 TradingAgents 自己的免责立场）。
- 评测/实验/决策全留痕，eval 分层演进。

## 3. 主要差距（需要补强）

| # | 差距 | 谁做得好 | 我们的动作 |
| --- | --- | --- | --- |
| G1 | **回测-实盘一致性**：同一套决策代码 + 统一接口跑回测与实盘，drift 只来自真实摩擦而非代码分叉 | FinRL-X 权重统一接口；Nautilus 同一套 actor | 立为原则(ADR-0003)，写入 M3/M5 交付物 |
| G2 | **预交易风控门**：所有订单必过风控校验(仓位/名义/**下单频率**)，不通过即拒绝 | Nautilus RiskEngine→OrderDenied；FinRL-X 三级风控 | M5 增设独立预交易风控门 + "无订单绕过"不变量 |
| G3 | **执行对账**：内部状态与券商实际订单/持仓对齐(漏单/重启恢复) | Nautilus LiveExecutionEngine | M5 引入(模拟盘版)，Gate/阶段7 强化 |
| G4 | **崩溃恢复/状态持久化**：进程重启后可恢复，crash-only 设计 | Nautilus + Redis | M5/阶段7 增加韧性要求 |
| G5 | **站在开源肩膀上**：复用成熟回测/执行引擎，并以开源框架作对照基准 | bt/vectorbt/Nautilus/Lean | ADR-0002 决策；M3 复用引擎；M6 对照 TradingAgents/ai-hedge-fund/FinRL |
| G6 | **regime/模型衰减检测**：分布漂移导致策略失效，需主动检测 + 刷新策略 | FinRL 明确 distribution shift 警告 | M6 增加 regime 检测 + 刷新/退役策略 |
| G7 | **LLM 成本经济学具体化**：单票单次分析约 $0.30–0.50(GPT-5)，DeepSeek/本地 Ollama 可降 80–90% | 通用经验 | 写入 CHARTER 预算 + M4 成本门；优先便宜后端 |

## 4. 关键现实校验（来自社区实测，写进预期管理）

- **回测-实盘落差巨大**：50% 回测年化在真实摩擦后常降到 10–15%，Sharpe 边际的策略实盘易转负。TradingAgents 一次 30 天实测 ~7% vs 标普 4.5%，但伴随 **22% 回撤**，且不可重复。
- **公开信息 alpha 很难**：LLM 从公开新闻/财报提取的信号，往往已被市场定价——这是对我们核心 Edge 假设的最大挑战。
- **LLM 保守偏差**：LLM 读过大量风险管理/黑天鹅文献，倾向过度谨慎，未必是正确信号。
- **成本吃掉收益**：round-trip 交易成本约 15–40 bps；叠加 LLM/数据成本，净收益可能为负。
- **官方立场**：TradingAgents/FinRL 作者均**不建议真金白银使用**，CFTC 警告过"AI 交易高收益"骗局。这些是研究/学习工具优先。

## 5. 我们的取舍（决策指引）

- **抄**：FinRL-X 的回测-实盘统一接口与三级风控；Nautilus 的对账/预交易风控门/崩溃恢复；开源框架作对照基准。
- **避**：让 LLM 自主下单（坚持混合红线）；零成本回测；一次验证永久有效（忽视 regime 衰减）；从零手搓回测引擎（除非有充分理由）。
- **补**：G1–G7 已分派到对应里程碑（见 [MILESTONES.md](MILESTONES.md)）。
- **待人类拍板**：是否复用成熟引擎 vs 自建（见 [decisions/0002-leverage-oss-vs-build.md](decisions/0002-leverage-oss-vs-build.md)）。
