# examples/

可直接运行的**离线**示例（零 API key、零联网）。每个脚本对应 README §13 的一段，并有单测背书。

```bash
uv sync --dev
uv run python examples/01_offline_backtest.py
```

| 脚本 | 演示 | 对应单测 |
| --- | --- | --- |
| `01_offline_backtest.py` | 确定性回测 → 权益曲线 + 指标 | `test_backtest_runner.py` |
| `02_signal_extraction.py` | AI 网关 + 预算熔断 + 缓存 + 情绪抽取 | `test_m7_pipeline.py` |
| `03_paper_loop.py` | 完整模拟盘闭环（信号→决策→风控→执行→对账） | `test_trading_loop.py` |
| `04_signal_eval.py` | 信号质量评测（IC / 显著性 / 保守偏差） | `test_signal_eval.py` |
| `05_anti_overfitting.py` | walk-forward + DSR + PBO + 留出集守卫 | `test_validation.py` · `test_overfit.py` |
| `06_go_live_governance.py` | 上线闸门 + 放量/回滚 + 防篡改审计 | `test_golive.py` · `test_ramp.py` · `test_audit.py` |
| `plot_equity.py` | 生成权益曲线图（需 `--extra viz`） | — |

> 合成/示例数据仅用于演示，**不构成任何真实 alpha 证据**。真实数据实证见 `docs/experiments/`。
>
> 也可用 CLI：`uv run atrading backtest --days 180`、`uv run atrading gate`。
