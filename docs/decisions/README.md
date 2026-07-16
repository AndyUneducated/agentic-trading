# 架构决策记录（ADR）

记录有长期影响的技术/架构/流程决策，让人与代理都能追溯"当时为什么这么选"。

- 每个决策一个文件：`NNNN-简短标题.md`，编号递增。
- 用 [adr-template.md](adr-template.md) 起草。
- 状态：Proposed / Accepted / Superseded。被取代时在旧 ADR 顶部标注取代它的编号。

## 索引

| 编号 | 标题 | 状态 |
| --- | --- | --- |
| [0001](0001-llm-positioning-hybrid.md) | LLM 定位采用混合架构（信号层，不下单） | Accepted |
| [0002](0002-leverage-oss-vs-build.md) | 复用成熟开源引擎 vs 自建（选 B：复用） | Accepted |
| [0003](0003-backtest-live-parity.md) | 回测-实盘一致（统一决策接口） | Accepted |
| [0004](0004-tech-stack.md) | 技术栈（Python/uv/Pydantic/…） | Accepted |
