from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from atrading.backtest.runner import BacktestResult, EquityPoint
from atrading.core.manifest import RunManifest
from atrading.eval import (
    GoLiveScorecard,
    build_edge_criteria,
    evaluate_oos_metrics,
    render_report,
)
from atrading.eval.scorecard import CharterThresholds
from atrading.eval.signal_eval import SignalEvalResult


def _result(equity: list[float]) -> BacktestResult:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    curve = [EquityPoint(ts=base + timedelta(days=i), equity=v) for i, v in enumerate(equity)]
    return BacktestResult(
        manifest=RunManifest(seed=0),
        initial_cash=equity[0],
        final_equity=equity[-1],
        equity_curve=curve,
    )


def test_build_edge_criteria_confirms_when_beating_all() -> None:
    strategy = _result([100.0, 130.0])
    baselines = {
        "zero": _result([100.0, 100.0]),
        "price_only": _result([100.0, 110.0]),
        "buy_hold": _result([100.0, 120.0]),
    }
    signal = SignalEvalResult(n=100, ic=0.1, rank_ic=0.1, hit_rate=0.6, ic_t_stat=3.0)
    edge = build_edge_criteria(strategy=strategy, baselines=baselines, signal=signal)
    assert edge.edge_confirmed


def test_edge_not_confirmed_without_significance() -> None:
    strategy = _result([100.0, 130.0])
    baselines = {
        "zero": _result([100.0, 100.0]),
        "price_only": _result([100.0, 110.0]),
        "buy_hold": _result([100.0, 120.0]),
    }
    weak_signal = SignalEvalResult(n=100, ic=0.01, rank_ic=0.0, hit_rate=0.5, ic_t_stat=0.5)
    edge = build_edge_criteria(strategy=strategy, baselines=baselines, signal=weak_signal)
    assert not edge.edge_confirmed


def test_go_live_scorecard_requires_all_green() -> None:
    strategy = _result([100.0, 130.0])
    baselines = {
        "zero": _result([100.0, 100.0]),
        "price_only": _result([100.0, 110.0]),
        "buy_hold": _result([100.0, 120.0]),
    }
    signal = SignalEvalResult(n=100, ic=0.1, rank_ic=0.1, hit_rate=0.6, ic_t_stat=3.0)
    edge = build_edge_criteria(strategy=strategy, baselines=baselines, signal=signal)

    all_green = GoLiveScorecard(
        edge=edge,
        oos_metrics_pass=True,
        dsr_pass=True,
        pbo_pass=True,
        net_of_all_costs_positive=True,
        drift_within_bounds=True,
        guardrails_verified=True,
    )
    assert all_green.go

    one_red = all_green.model_copy(update={"guardrails_verified": False})
    assert not one_red.go


def test_evaluate_oos_metrics_drawdown_gate() -> None:
    # 大回撤应判不达标（回撤 50% > 20% 上限）。
    crashy = _result([100.0, 150.0, 75.0, 80.0])
    assert not evaluate_oos_metrics(crashy, CharterThresholds())


def test_render_report_writes_markdown(tmp_path: Path) -> None:
    strategy = _result([100.0, 130.0])
    baselines = {"zero": _result([100.0, 100.0])}
    path = render_report(strategy, baselines, out_dir=tmp_path, strategy_name="mvp")
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "评测报告" in content
    assert "mvp" in content
