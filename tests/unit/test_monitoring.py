from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atrading.eval import oss_baseline_from_equity
from atrading.monitoring import (
    DriftReport,
    RefreshPolicy,
    RegimeMonitor,
    compute_drift,
)


def test_regime_no_shift_when_identical() -> None:
    ref = {"AAA": [0.01, -0.01, 0.02, -0.02], "BBB": [0.01, -0.01, 0.02, -0.02]}
    report = RegimeMonitor().detect_shift(ref, ref)
    assert not report.shifted
    assert report.vol_ratio == pytest.approx(1.0)


def test_regime_detects_volatility_blowup() -> None:
    ref = {"AAA": [0.001, -0.001, 0.001, -0.001]}
    recent = {"AAA": [0.05, -0.06, 0.07, -0.05]}
    report = RegimeMonitor(vol_ratio_threshold=1.5).detect_shift(recent, ref)
    assert report.shifted
    assert report.vol_ratio > 1.5


def test_refresh_policy_actions() -> None:
    policy = RefreshPolicy(min_live_days_before_refresh=20, action_on_shift="reduce_exposure")
    from atrading.monitoring import RegimeReport

    calm = RegimeReport(vol_ratio=1.0, corr_shift=0.0, shifted=False)
    assert policy.decide(calm, live_days=100) == "hold"

    shifted = RegimeReport(vol_ratio=2.0, corr_shift=0.4, shifted=True)
    assert policy.decide(shifted, live_days=5) == "alert"  # 样本不足 → 仅告警
    assert policy.decide(shifted, live_days=50) == "reduce_exposure"


def test_drift_zero_when_live_equals_backtest() -> None:
    weights = [{"AAA": 0.2}, {"AAA": 0.2}]
    equity = [100.0, 105.0]
    report = compute_drift(weights, weights, equity, equity)
    assert report.weight_l1 == pytest.approx(0.0)
    assert report.return_gap == pytest.approx(0.0)
    assert report.within_bounds


def test_drift_detects_divergence() -> None:
    live_w = [{"AAA": 0.9}]
    bt_w = [{"AAA": 0.1}]
    report = compute_drift(live_w, bt_w, [100.0, 90.0], [100.0, 120.0])
    assert not report.within_bounds
    assert report.weight_l1 > 0.05
    assert isinstance(report, DriftReport)


def test_oss_baseline_from_equity() -> None:
    ts = [datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=i) for i in range(3)]
    result = oss_baseline_from_equity("TradingAgents", ts, [100.0, 110.0, 121.0])
    assert result.final_equity == 121.0
    assert result.equity_values() == [100.0, 110.0, 121.0]

    with pytest.raises(ValueError, match="长度必须一致"):
        oss_baseline_from_equity("x", ts, [100.0, 110.0])
