<!-- 标题请遵循 Conventional Commits：feat/fix/docs/refactor/test/chore/exp -->

## 动机 / 背景
<!-- 为什么做这个改动？关联 issue：Closes #___ -->

## 改动内容
<!-- 简述关键改动（bullet points） -->
-

## 如何验证
<!-- 命令 / 新增测试 / 评测结果 -->
- [ ] `uv run ruff check src tests examples`
- [ ] `uv run ruff format --check src tests examples`
- [ ] `uv run mypy`
- [ ] `uv run pytest`

## 红线自检
- [ ] 未让运行时 LLM 直接下单（ADR-0001）
- [ ] 未引入密钥/凭证；未使用未来数据（point-in-time）
- [ ] 涉及策略/信号：有样本外、扣成本、对照基线的证据（`docs/experiments/`）
- [ ] 有长期架构影响：已新增/更新 ADR（`docs/decisions/`）

## 补充说明
<!-- 取舍、后续工作、已知限制 -->
