# 安全策略 (Security Policy)

## 报告漏洞

请**不要**通过公开 issue 报告安全问题。请使用 GitHub 的
[Private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
（仓库 **Security → Report a vulnerability**）私下提交。

我们会尽力在合理时间内确认并跟进。

## 本项目特有的安全关注点

这是一个可能接触**资金与市场**的系统，除常规软件安全外，请特别注意：

| 类别 | 关注点 |
| --- | --- |
| **凭证** | 绝不把 API key / 账户凭证写入代码或提交 git。只用 `.env`（见 `.env.example`）。CI 有 gitleaks 扫描。 |
| **交易护栏** | 不得绕过 `PreTradeRiskGate`；不得让运行时 LLM 直接产生订单动作（ADR-0001）。 |
| **Prompt 注入** | LLM 读取的外部非结构化信息（新闻等）视为**不可信输入**，须隔离与校验（见 `signals/sanitize.py`）；不得让其改变系统指令或触发越权动作。 |
| **实盘资金** | 默认 `TRADING_MODE=paper`；接入真实资金需明确人类批准与上线闸门（`governance/`）。 |
| **KILL_SWITCH** | `KILL_SWITCH=true` 必须能立即禁止任何下单。 |

## 负责任披露

在修复发布前，请勿公开漏洞细节。感谢你帮助保障本项目与其使用者的安全。
