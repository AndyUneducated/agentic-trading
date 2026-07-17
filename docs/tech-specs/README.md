# 技术方案（Tech Specs）— 共享约定

> 本目录为 M1–M10 的**详细技术方案**，外加跨阶段的 [EVAL-framework.md](EVAL-framework.md)。
> 本文件承载所有技术方案共享的：技术栈、仓库结构、**核心接口契约**、AI-coding 工作流。各里程碑文档只写自己的增量，避免重复。

## 0. 阅读顺序与索引

| 文档 | 里程碑 | 内容 |
| --- | --- | --- |
| 本文件 | — | 技术栈、仓库结构、核心契约、AI-coding 工作流 |
| [M1-workspace-and-tooling.md](M1-workspace-and-tooling.md) | M1 | 工程环境、工具链、CI、配置、密钥、代理上下文 |
| [M2-strategy-and-signal-contract.md](M2-strategy-and-signal-contract.md) | M2 | 策略假设与信号契约的类型化建模 |
| [M3-data-and-backtest.md](M3-data-and-backtest.md) | M3 | 数据层(PIT) + 回测引擎(复用) + 统一决策接口 |
| [EVAL-framework.md](EVAL-framework.md) | 跨阶段 | 指标、验证切分、防过拟合、报告 |
| [M4-llm-signal-layer.md](M4-llm-signal-layer.md) | M4 | LLM 信号层：客户端/提取器/缓存/信号评测/prompt 版本化 |
| [M5-decision-execution-paper.md](M5-decision-execution-paper.md) | M5 | 决策层 + 预交易风控门 + 模拟盘执行 + 对账 + 崩溃恢复 |
| [M6-experimentation-and-validation.md](M6-experimentation-and-validation.md) | M6 | 实验框架 + 样本外验证 + regime/drift 监控 + 开源基准对比 |
| [M7-real-integrations.md](M7-real-integrations.md) | M7 | 真实数据源 + 真实 LLM + AI gateway + PIT 时序隔离（生产化） |
| [M8-production-execution-engine.md](M8-production-execution-engine.md) | M8 | 采用 Nautilus 的生产执行引擎 + 真实 paper 券商（生产化） |
| [M9-observability-and-ops.md](M9-observability-and-ops.md) | M9 | 指标/tracing/告警 + 容器化 + 密钥托管 + incident playbook（生产化） |
| [M10-compliance-and-go-live.md](M10-compliance-and-go-live.md) | M10 | 合规要件 + 上线闸门记分卡 + 小额实盘/放量/回滚（生产化） |

> **状态**：M1–M6 + EVAL + **M9 可观测性核心**已实现并全绿（137 测试，离线优先）；示例代码与实际实现基本一致。**M7/M8/M10 为提案**（生产化路线，见 [PRODUCTION-READINESS.md](../PRODUCTION-READINESS.md)），其示例代码是"目标接口"。

## 1. 技术栈（见 ADR-0004，Accepted）

| 领域 | 选型 | 理由 / 备选 |
| --- | --- | --- |
| 语言 | Python 3.11+ | 领域标准；所有对标项目均 Python |
| 包/环境管理 | uv | 快、锁定可复现；备选 Poetry |
| 类型化数据/配置 | Pydantic v2 + pydantic-settings | 契约优先、`.env` 类型安全（对标 FinRL-X） |
| 数据处理 | pandas + pyarrow(parquet) | 生态成熟；大数据量可后续引 polars |
| 回测引擎 | **复用**（vectorbt / bt；实盘一致场景评估 Nautilus）见 ADR-0002(Accepted) | 不手搓，藏在我们统一接口后 |
| LLM 客户端 | 供应商无关薄封装（OpenAI/Anthropic/DeepSeek/Ollama） | 成本可切换；结构化输出用 pydantic |
| 券商/执行 | Alpaca（paper，美股/ETF/加密）+ CCXT（加密） | 见 CHARTER 候选 |
| 测试 | pytest + hypothesis(可选) | 单元 + golden/合成用例 |
| 结构化日志 | structlog | 决策/交易可追溯 |
| 实验/指标追踪 | 文件式(parquet/json)+git；可选 MLflow | 轻量、可复现优先 |
| 代码质量 | ruff(lint+format) + mypy(类型) | CI 强制 |
| CI | GitHub Actions | lint/type/test/eval 门禁 |

## 2. 仓库结构（提案）

工程代码在 M3 起逐步引入 `src/`。采用单包 `atrading`，按领域分层：

```text
agentic-trading/
├── src/atrading/
│   ├── config/          # pydantic-settings，环境与密钥加载
│   ├── core/            # 领域类型 + 接口契约（最先稳定）
│   │   ├── types.py     # Bar, Signal, TargetWeights, Order, Fill, PortfolioState
│   │   └── interfaces.py# DataSource, SignalSource, DecisionPolicy, RiskGate, Broker, Clock
│   ├── data/            # 数据层（M3）：providers/ 适配器 + PIT store
│   ├── backtest/        # 回测（M3）：复用引擎 + 统一决策接口驱动
│   ├── eval/            # 评测框架（跨阶段）：metrics/validation/report
│   ├── signals/         # LLM 信号层（M4）：llm_client/extractors/cache
│   ├── decision/        # 规则/量化决策（M5）：policy(统一接口) + sizing
│   ├── risk/            # 预交易风控门 + kill switch（M5）
│   ├── execution/       # 券商适配 + 对账 + 恢复（M5）
│   ├── experiments/     # 实验编排（M6）
│   ├── monitoring/      # drift/regime/成本监控（M5/M6）
│   └── cli.py           # 入口命令
├── tests/{unit,golden,fixtures}/
├── configs/             # 环境配置（yaml）
├── prompts/             # 版本化 prompt（M4）
└── pyproject.toml
```

## 3. 核心接口契约（contracts-first，最先稳定）

这是全系统的"宪法"。**先把这些类型与接口定稳，代理据此并行实现各模块并可 mock 依赖。** 回测与实盘共用同一 `DecisionPolicy`（ADR-0003）。

```python
# core/types.py  —— 目标接口，示意
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

class Bar(BaseModel):
    symbol: str
    ts: datetime            # UTC，bar 收盘时刻
    open: float; high: float; low: float; close: float; volume: float

class Signal(BaseModel):
    symbol: str
    as_of: datetime         # 信号"当时可用"时刻（PIT）
    name: str               # 因子名
    value: float
    confidence: float = Field(ge=0, le=1)
    model_version: str | None = None
    prompt_version: str | None = None
    rationale: str | None = None

class TargetWeights(BaseModel):
    as_of: datetime
    weights: dict[str, float]   # symbol -> 目标组合权重（Σ|w| 受约束）

class Order(BaseModel):
    symbol: str
    side: Literal["buy", "sell"]
    qty: float
    type: Literal["market", "limit"] = "market"
    limit_price: float | None = None
    client_order_id: str            # 幂等键，用于对账/恢复

class Fill(BaseModel):
    client_order_id: str
    symbol: str; qty: float; price: float; ts: datetime; fee: float

class PortfolioState(BaseModel):
    ts: datetime
    cash: float
    positions: dict[str, float]     # symbol -> 数量
    equity: float
```

```python
# core/interfaces.py —— Protocol，便于 mock 与并行实现
from typing import Protocol, Iterable
from datetime import datetime

class Clock(Protocol):
    def now(self) -> datetime: ...          # 回测=模拟时钟，实盘=真实时钟

class DataSource(Protocol):
    def get_bars(self, symbols: list[str], start: datetime, end: datetime,
                 freq: str) -> Iterable[Bar]: ...
    # 约束：只返回 as_of<=now 的数据（PIT，无未来函数）

class SignalSource(Protocol):
    def signals_as_of(self, ts: datetime, symbols: list[str]) -> list[Signal]: ...

class DecisionContext(BaseModel):
    as_of: datetime
    bars: dict[str, list[Bar]]          # 截至 as_of 的历史
    signals: list[Signal]
    portfolio: PortfolioState

class DecisionPolicy(Protocol):
    """统一决策接口（ADR-0003）：回测与实盘调用同一实现。"""
    def decide(self, ctx: DecisionContext) -> TargetWeights: ...

class RiskDecision(BaseModel):
    approved: list[Order]
    denied: list[tuple[Order, str]]     # (订单, 拒绝原因)

class RiskGate(Protocol):
    def check(self, orders: list[Order], portfolio: PortfolioState) -> RiskDecision: ...

class Broker(Protocol):
    def submit(self, order: Order) -> None: ...
    def get_positions(self) -> PortfolioState: ...
    def get_open_orders(self) -> list[Order]: ...
    def get_fills(self, since: datetime) -> list[Fill]: ...
```

**关键不变量**：
- 订单 → 执行之间**必过** `RiskGate`；`execution` 层不接受未经风控的订单。
- `DecisionPolicy.decide` 是**纯函数**（同 `ctx` → 同 `TargetWeights`），不做 IO、不看未来——这是可回测、可复现、回测-实盘一致的根基。
- 所有跨越时间的读取都通过 `Clock` + PIT `DataSource`，杜绝 look-ahead。

## 4. AI-coding 工作流（每个模块都照此执行）

面向 AI 编码代理的最佳实践，落到每个 PR：

1. **契约先行**：先在 `core/` 定/改类型与 Protocol，评审通过再实现（接口是 human↔agent 的对齐点）。
2. **测试先行/同行**：为接口写单元测试 + 至少一个 golden/合成用例；外部依赖用 mock（Broker/LLM/DataSource 都可替身）。
3. **评测门禁**：涉及信号/策略的改动必须能被 `eval/` 打分（见 EVAL 文档），无评测不合并。
4. **小 PR、单一职责**：一个 PR 一个模块/一个变量；Conventional Commits。
5. **可复现**：固定种子、记录数据/代码/模型/prompt 版本（元数据规范见 M1）。
6. **确定性优先**：核心决策与回测确定性；不确定性（LLM）隔离在 `signals/` 且缓存+留痕。
7. **每个模块自带"完成定义"**：映射到里程碑准出指标（见 MILESTONES）。

### 通用"实现任务分解"模板（供代理拆 PR）
```text
1) 定义/更新 core 契约 + 类型测试
2) 实现 fake/mock 版依赖（便于隔离测试）
3) 实现模块逻辑（纯函数优先）
4) 单元测试 + golden 用例
5) 接入 eval / 报告
6) 文档：更新对应 spec 与 CHANGELOG
```

## 5. 与高层规格的关系
- 业务口径以 `docs/specs/`（strategy-hypothesis / llm-signal / backtest-eval）与 `docs/PROJECT_CHARTER.md` 为准。
- 决策记录见 `docs/decisions/`（ADR-0001 混合红线、0002 复用开源、0003 回测-实盘一致、0004 技术栈）。
- 本目录只谈"怎么实现"，不改业务口径。
