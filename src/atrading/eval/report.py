"""一键评测报告（markdown，可复现）。

产出 runs/<run_id>/report.md：策略 vs 多基准的指标表、回撤、换手/成本口径与
RunManifest（数据/代码/参数版本），便于人工复核与实验间 diff。选 markdown 而非 HTML：
纯文本、易 diff、CI artifact 友好、无额外依赖（符合"可复现+轻量"原则）。
"""

from __future__ import annotations

from pathlib import Path

from atrading.backtest.runner import BacktestResult
from atrading.eval.metrics import (
    excess_return,
    max_drawdown,
    returns_from_equity,
    sharpe,
    sortino,
    total_return,
)


def _metrics_row(name: str, result: BacktestResult) -> str:
    equity = result.equity_values()
    rets = returns_from_equity(equity)
    return (
        f"| {name} | {total_return(equity):.4f} | {max_drawdown(equity):.4f} "
        f"| {sharpe(rets):.3f} | {sortino(rets):.3f} | {result.final_equity:.2f} |"
    )


def render_report(
    result: BacktestResult,
    baselines: dict[str, BacktestResult],
    *,
    out_dir: str | Path = "runs",
    strategy_name: str = "strategy",
) -> Path:
    manifest = result.manifest
    run_dir = Path(out_dir) / manifest.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append(f"# 评测报告 · {strategy_name}")
    lines.append("")
    lines.append("## Run manifest")
    lines.append("")
    lines.append(f"- run_id: `{manifest.run_id}`")
    lines.append(f"- git_commit: `{manifest.git_commit}`")
    lines.append(f"- data_version: `{manifest.data_version}`")
    lines.append(f"- seed: `{manifest.seed}`")
    lines.append(f"- params: `{manifest.params}`")
    lines.append("")
    lines.append("## 指标（策略 vs 基准）")
    lines.append("")
    lines.append("| 名称 | 总收益 | 最大回撤 | Sharpe | Sortino | 期末权益 |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    lines.append(_metrics_row(strategy_name, result))
    for name, base in baselines.items():
        lines.append(_metrics_row(name, base))
    lines.append("")
    lines.append("## 相对基准超额（总收益差）")
    lines.append("")
    strat_equity = result.equity_values()
    for name, base in baselines.items():
        lines.append(f"- vs {name}: {excess_return(strat_equity, base.equity_values()):+.4f}")
    lines.append("")
    lines.append("> 注：以成本后口径为准；DSR/PBO 与最终留出判定见 scorecard。")
    lines.append("")

    report_path = run_dir / "report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path
