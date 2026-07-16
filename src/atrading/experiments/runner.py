"""实验编排：单变量、可复现、自动记账。

强制**单变量**（overrides 只允许一个键）——防"一次改一堆说不清谁有用"。结果带
RunManifest，可复现；写入 docs/experiments/ 形成证据链。指标与基线复用 EVAL 框架。
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator

from atrading.backtest.costs import CostModel
from atrading.backtest.runner import BacktestResult, BacktestRunner
from atrading.core.interfaces import DataSource, DecisionPolicy, SignalSource
from atrading.core.manifest import RunManifest
from atrading.core.strategy_config import StrategyConfig
from atrading.eval.baselines import run_baselines
from atrading.eval.metrics import (
    max_drawdown,
    returns_from_equity,
    sharpe,
    sortino,
    total_return,
)
from atrading.eval.validation import DateRange

BuildPolicy = Callable[[StrategyConfig, dict[str, Any]], DecisionPolicy]


class ExperimentSpec(BaseModel):
    name: str
    hypothesis: str
    variable: str  # 本次唯一改变量（必须与 overrides 的唯一键一致）
    base_config: StrategyConfig
    overrides: dict[str, Any] = Field(default_factory=dict)
    period: DateRange
    seed: int = 0

    @model_validator(mode="after")
    def _enforce_single_variable(self) -> ExperimentSpec:
        if len(self.overrides) != 1:
            msg = f"实验必须单变量：overrides 恰好 1 个键，实际 {len(self.overrides)} 个"
            raise ValueError(msg)
        if self.variable not in self.overrides:
            msg = f"variable={self.variable!r} 必须是 overrides 的键"
            raise ValueError(msg)
        return self


class ExperimentResult(BaseModel):
    spec_name: str
    strategy: str
    manifest: RunManifest
    strategy_metrics: dict[str, float]
    baseline_metrics: dict[str, dict[str, float]] = Field(default_factory=dict)
    conclusion: str | None = None


def result_metrics(result: BacktestResult) -> dict[str, float]:
    equity = result.equity_values()
    rets = returns_from_equity(equity)
    return {
        "total_return": total_return(equity),
        "max_drawdown": max_drawdown(equity),
        "sharpe": sharpe(rets),
        "sortino": sortino(rets),
    }


def run_experiment(
    spec: ExperimentSpec,
    *,
    data: DataSource,
    costs: CostModel,
    build_policy: BuildPolicy,
    signals: SignalSource | None = None,
    initial_cash: float = 100_000.0,
) -> ExperimentResult:
    policy = build_policy(spec.base_config, spec.overrides)
    manifest = RunManifest(
        seed=spec.seed,
        params={"experiment": spec.name, "variable": spec.variable, **spec.overrides},
    )
    result = BacktestRunner(
        policy=policy,
        data=data,
        costs=costs,
        config=spec.base_config,
        signals=signals,
        seed=spec.seed,
        initial_cash=initial_cash,
    ).run(spec.period.start, spec.period.end)

    baselines = run_baselines(
        data=data,
        config=spec.base_config,
        costs=costs,
        start=spec.period.start,
        end=spec.period.end,
        initial_cash=initial_cash,
    )
    return ExperimentResult(
        spec_name=spec.name,
        strategy=spec.base_config.name,
        manifest=manifest,
        strategy_metrics=result_metrics(result),
        baseline_metrics={name: result_metrics(res) for name, res in baselines.items()},
    )


def write_experiment_log(
    spec: ExperimentSpec,
    result: ExperimentResult,
    *,
    out_dir: str | Path = "docs/experiments",
) -> Path:
    """按模板把实验写入 docs/experiments/<date>-<name>.md，形成证据链。"""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    date = datetime.now(tz=result.manifest.created_at.tzinfo).strftime("%Y%m%d")
    path = out / f"{date}-{spec.name}.md"

    sm = result.strategy_metrics
    lines = [
        f"# 实验：{spec.name}（{date}）",
        "",
        "- 关联里程碑 / 规格：M6",
        f"- 变更的单一变量：`{spec.variable}` = `{spec.overrides[spec.variable]}`",
        f"- code_version(commit)：`{result.manifest.git_commit}`",
        f"- seed：`{spec.seed}`",
        "",
        "## 假设（Hypothesis）",
        "",
        spec.hypothesis,
        "",
        "## 结果（Results）",
        "",
        "| 指标 | 本实验 | zero | price_only | buy_hold |",
        "| --- | --- | --- | --- | --- |",
    ]
    for metric in ("total_return", "max_drawdown", "sharpe", "sortino"):
        row = [f"{sm.get(metric, 0.0):.4f}"]
        for name in ("zero", "price_only", "buy_hold"):
            row.append(f"{result.baseline_metrics.get(name, {}).get(metric, 0.0):.4f}")
        lines.append(f"| {metric} | " + " | ".join(row) + " |")
    lines += [
        "",
        "## 结论（Conclusion）",
        "",
        result.conclusion or "（待人工填写：假设是否成立 / 是否采纳 / 下一个变量 / 过拟合存疑点）",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
