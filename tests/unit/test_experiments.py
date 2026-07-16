from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from atrading.backtest import CostModel
from atrading.core.manifest import RunManifest
from atrading.core.strategy_config import StrategyConfig
from atrading.core.types import Bar
from atrading.data import InMemoryDataSource
from atrading.decision import PassthroughSizer, RulesDecisionPolicy
from atrading.eval import deflated_sharpe_ratio
from atrading.eval.validation import DateRange
from atrading.experiments import (
    ExperimentRegistry,
    ExperimentResult,
    ExperimentSpec,
    run_experiment,
    write_experiment_log,
)


def _series(symbol: str, closes: list[float]) -> list[Bar]:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        Bar(symbol=symbol, ts=base + timedelta(days=i), open=c, high=c, low=c, close=c, volume=1.0)
        for i, c in enumerate(closes)
    ]


def _spec(**overrides: Any) -> ExperimentSpec:
    return ExperimentSpec(
        name="thr-test",
        hypothesis="更高情绪阈值过滤噪声，提升样本外表现",
        variable="sentiment_threshold",
        base_config=StrategyConfig(name="mvp", universe=["AAA", "BBB"], decision_freq="daily"),
        overrides=overrides or {"sentiment_threshold": 0.1},
        period=DateRange(
            start=datetime(2026, 1, 1, tzinfo=UTC), end=datetime(2026, 1, 5, tzinfo=UTC)
        ),
        seed=7,
    )


def _build_policy(config: StrategyConfig, ov: dict[str, Any]) -> RulesDecisionPolicy:
    return RulesDecisionPolicy(
        config,
        PassthroughSizer(config),
        sentiment_threshold=float(ov.get("sentiment_threshold", 0.0)),
    )


def test_single_variable_enforced() -> None:
    with pytest.raises(ValidationError, match="单变量"):
        ExperimentSpec(
            name="bad",
            hypothesis="h",
            variable="sentiment_threshold",
            base_config=StrategyConfig(name="mvp", universe=["AAA"], decision_freq="daily"),
            overrides={"sentiment_threshold": 0.1, "lookback": 5},
            period=DateRange(
                start=datetime(2026, 1, 1, tzinfo=UTC), end=datetime(2026, 1, 5, tzinfo=UTC)
            ),
        )


def test_variable_must_match_override_key() -> None:
    with pytest.raises(ValidationError, match="必须是 overrides 的键"):
        ExperimentSpec(
            name="bad",
            hypothesis="h",
            variable="lookback",
            base_config=StrategyConfig(name="mvp", universe=["AAA"], decision_freq="daily"),
            overrides={"sentiment_threshold": 0.1},
            period=DateRange(
                start=datetime(2026, 1, 1, tzinfo=UTC), end=datetime(2026, 1, 5, tzinfo=UTC)
            ),
        )


def test_run_experiment_produces_metrics_and_baselines() -> None:
    data = InMemoryDataSource(
        _series("AAA", [100.0, 102.0, 104.0, 106.0, 108.0])
        + _series("BBB", [100.0, 99.0, 98.0, 97.0, 96.0])
    )
    result = run_experiment(
        _spec(),
        data=data,
        costs=CostModel(commission_bps=0.0, slippage_bps=0.0),
        build_policy=_build_policy,
        signals=None,
    )
    assert set(result.strategy_metrics) == {"total_return", "max_drawdown", "sharpe", "sortino"}
    assert set(result.baseline_metrics) == {"zero", "price_only", "buy_hold"}
    assert result.strategy == "mvp"
    assert result.manifest.params["variable"] == "sentiment_threshold"


def test_write_experiment_log(tmp_path: Path) -> None:
    data = InMemoryDataSource(_series("AAA", [100.0, 101.0, 102.0, 103.0, 104.0]))
    spec = _spec()
    result = run_experiment(
        spec,
        data=data,
        costs=CostModel(commission_bps=0.0, slippage_bps=0.0),
        build_policy=_build_policy,
    )
    path = write_experiment_log(spec, result, out_dir=tmp_path)
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "thr-test" in content
    assert "sentiment_threshold" in content


def test_registry_counts_trials_and_persists(tmp_path: Path) -> None:
    reg_path = tmp_path / "registry.jsonl"
    registry = ExperimentRegistry(reg_path)

    def _make() -> ExperimentResult:
        return ExperimentResult(
            spec_name="e",
            strategy="mvp",
            manifest=RunManifest(seed=0),
            strategy_metrics={"sharpe": 0.1},
        )

    registry.record(_make())
    registry.record(_make())
    assert registry.n_trials("mvp") == 2
    assert registry.n_trials("other") == 0

    # 跨会话：新 registry 从磁盘恢复 n_trials。
    reopened = ExperimentRegistry(reg_path)
    assert reopened.n_trials("mvp") == 2


def test_n_trials_penalizes_dsr() -> None:
    sr = 0.2
    dsr_few = deflated_sharpe_ratio(sr, n_trials=1, n_obs=252)
    dsr_many = deflated_sharpe_ratio(sr, n_trials=50, n_obs=252)
    assert dsr_many < dsr_few  # 试验越多，同一 Sharpe 越不可信
