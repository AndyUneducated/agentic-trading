from __future__ import annotations

from atrading.governance.ramp import CapitalRampController, LiveStage, RampConfig


def test_promotes_when_scorecard_green_and_observed() -> None:
    ctrl = CapitalRampController(config=RampConfig(min_days_per_stage=5))
    decision = ctrl.evaluate(scorecard_go=True, live_drawdown=0.0, drift_ok=True, days_at_stage=5)
    assert decision.action == "promote"
    assert decision.from_stage == LiveStage.paper
    assert decision.to_stage == LiveStage.pilot
    assert ctrl.stage == LiveStage.pilot


def test_holds_before_observation_window() -> None:
    ctrl = CapitalRampController(config=RampConfig(min_days_per_stage=5))
    decision = ctrl.evaluate(scorecard_go=True, live_drawdown=0.0, drift_ok=True, days_at_stage=2)
    assert decision.action == "hold"
    assert ctrl.stage == LiveStage.paper


def test_soft_rollback_on_drawdown() -> None:
    config = RampConfig(soft_rollback_drawdown=0.1)
    ctrl = CapitalRampController(stage=LiveStage.ramp, config=config)
    decision = ctrl.evaluate(scorecard_go=True, live_drawdown=0.12, drift_ok=True, days_at_stage=9)
    assert decision.action == "rollback"
    assert decision.to_stage == LiveStage.pilot


def test_rollback_on_drift_breach() -> None:
    ctrl = CapitalRampController(stage=LiveStage.pilot)
    decision = ctrl.evaluate(scorecard_go=True, live_drawdown=0.0, drift_ok=False, days_at_stage=9)
    assert decision.action == "rollback"
    assert decision.to_stage == LiveStage.paper


def test_hard_halt_on_severe_drawdown() -> None:
    ctrl = CapitalRampController(stage=LiveStage.scaled, config=RampConfig(hard_halt_drawdown=0.2))
    decision = ctrl.evaluate(scorecard_go=True, live_drawdown=0.25, drift_ok=True, days_at_stage=9)
    assert decision.action == "halt"
    assert ctrl.stage == LiveStage.halted


def test_halted_requires_manual_reset() -> None:
    ctrl = CapitalRampController(stage=LiveStage.halted)
    decision = ctrl.evaluate(scorecard_go=True, live_drawdown=0.0, drift_ok=True, days_at_stage=99)
    assert decision.action == "hold"
    assert ctrl.stage == LiveStage.halted
    ctrl.reset(LiveStage.paper)
    assert ctrl.stage == LiveStage.paper


def test_no_promote_past_scaled() -> None:
    ctrl = CapitalRampController(stage=LiveStage.scaled)
    decision = ctrl.evaluate(scorecard_go=True, live_drawdown=0.0, drift_ok=True, days_at_stage=99)
    assert decision.action == "hold"
    assert ctrl.stage == LiveStage.scaled
