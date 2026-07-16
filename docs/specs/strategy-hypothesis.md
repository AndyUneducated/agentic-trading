# 规格：策略假设（Strategy Hypothesis）

> 状态：草案（在 M2 定稿）。目的是把"怎么赚钱"写成可回测、可证伪的假设。

## 1. Edge 假设

- 我们相信的信息/执行优势是：`TODO`
- 为什么它可能存在且未被完全套利：`TODO`

## 2. 证伪条件

- 若出现以下情况，则视为假设不成立：`TODO`（例如：加入 LLM 信号后相对价量基线无显著提升）。

## 3. 标的池

- 初始池（草案，定义于 [../../configs/strategies/mvp.yaml](../../configs/strategies/mvp.yaml)）：`SPY, QQQ`（宽基 ETF）、`AAPL, MSFT, NVDA`（高流动性美股）、`BTC-USD, ETH-USD`（加密）。
- 选取理由：流动性高、点差小、数据/新闻覆盖充分，利于控制滑点并保证 LLM 有足够非结构化信息。
- 待定：是否纳入更多标的、A/B 期的池差异（M2 评审时确认）。

## 4. 决策规格

- 决策周期：`TODO`（日内 / 日线 / 波段）
- 动作空间：`TODO`（买 / 卖 / 持有 / 目标仓位；是否允许做空）
- 再平衡频率与换手预算：`TODO`

## 5. 基准与评估指标

- 基准（须**同时**跑赢）：SPY / BTC 买入持有、**纯价量/技术基线**、一个**开源框架基线**（TradingAgents / ai-hedge-fund / FinRL，见 [../LANDSCAPE.md](../LANDSCAPE.md)）。
- 主指标：`TODO`（对齐 PROJECT_CHARTER 成功指标）。

## 6. 信号 → 决策的高层逻辑

- LLM 信号如何进入决策（详细映射在 M5 决策层规格）：`TODO`
