# 贡献指南 (Contributing)

感谢关注本项目。这是一个**研究导向**的混合架构 Agentic 交易系统；贡献前请先读 [`AGENTS.md`](AGENTS.md) 与 [`.cursor/rules/`](.cursor/rules/)（对人类协作者同样适用）。

## 核心约定（不可协商）

| 红线 | 说明 |
| --- | --- |
| **LLM 不下单** | 运行时 LLM 只产结构化信号；决策与下单只在确定性规则/量化层（ADR-0001）。 |
| **无评测不合并** | 任何策略/信号/prompt 改动必须能被评测/回测判定好坏（Eval-driven）。 |
| **默认 paper** | 默认 `TRADING_MODE=paper`；未经明确人类批准不接入真实资金。 |
| **密钥不入库** | 只用 `.env`（见 `.env.example`）；CI 有 gitleaks 扫描。 |
| **无未来函数** | 回测只用 point-in-time 数据；`as_of` 过滤，禁止 look-ahead。 |
| **防过拟合** | 走 walk-forward / purged CV / 留出集；不得反复调参而不做样本外验证。 |

## 开发环境

```bash
uv sync --dev
uv run ruff check src tests examples     # lint
uv run ruff format --check src tests examples
uv run mypy                              # 类型（strict）
uv run pytest                            # 全量测试
```

（可选）启用 pre-commit：`uv run pre-commit install`。

## 提交前自检清单

- [ ] `ruff check` / `ruff format --check` / `mypy` / `pytest` 全绿
- [ ] 新增/变更逻辑有对应测试（或评测）
- [ ] 涉及策略/信号：有样本外、扣成本、对照基线的证据（写入 `docs/experiments/`）
- [ ] 有长期影响的技术/架构选择：新增一条 ADR（`docs/decisions/`）
- [ ] 未引入密钥/凭证；未使用未来数据

## Git 约定

- 分支：`feat/*`、`fix/*`、`docs/*`、`exp/*`、`refactor/*`、`test/*`、`chore/*`。
- 提交信息：[Conventional Commits](https://www.conventionalcommits.org/)（`feat:` / `fix:` / `docs:` / `refactor:` / `test:` / `chore:` / `exp:`）。
- 小而聚焦的 PR，尽量对应一个可验证的小改动。

## PR 流程

1. Fork / 建分支 → 实现 → 本地门禁全绿。
2. 按 [PR 模板](.github/PULL_REQUEST_TEMPLATE.md) 填写动机、改动、验证方式。
3. CI（quality · eval-smoke · gitleaks）通过后请求评审。

## 报告问题

- Bug / 功能请用对应的 [Issue 模板](.github/ISSUE_TEMPLATE/)。
- **安全相关请勿公开提 issue**，见 [SECURITY.md](SECURITY.md)。
