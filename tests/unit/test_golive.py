"""上线闸门 eval（M10）：记分卡 + 人类批准 + kill switch 三重红线。"""

from __future__ import annotations

from atrading.core.falsification import EdgeCriteria
from atrading.eval.scorecard import GoLiveScorecard
from atrading.governance.golive import GoLiveGate


def _green_scorecard() -> GoLiveScorecard:
    edge = EdgeCriteria(
        beats_zero_baseline=True,
        beats_price_only=True,
        beats_buy_hold=True,
        beats_oss_baseline=True,
        significance_ok=True,
    )
    return GoLiveScorecard(
        edge=edge,
        oos_metrics_pass=True,
        dsr_pass=True,
        pbo_pass=True,
        net_of_all_costs_positive=True,
        drift_within_bounds=True,
        guardrails_verified=True,
    )


def test_allowed_only_with_green_scorecard_and_human_approval() -> None:
    gate = GoLiveGate(scorecard=_green_scorecard(), human_approved=True)
    assert gate.allowed
    assert gate.blockers() == []


def test_green_scorecard_but_no_human_approval_blocks() -> None:
    gate = GoLiveGate(scorecard=_green_scorecard(), human_approved=False)
    assert not gate.allowed  # 红线：绝不自动上线
    assert any("人类明确批准" in b for b in gate.blockers())


def test_kill_switch_blocks_even_if_approved() -> None:
    gate = GoLiveGate(scorecard=_green_scorecard(), human_approved=True, kill_switch_active=True)
    assert not gate.allowed
    assert any("KILL_SWITCH" in b for b in gate.blockers())


def test_failing_scorecard_blocks() -> None:
    scorecard = _green_scorecard()
    scorecard.dsr_pass = False  # 任一硬门槛未过
    gate = GoLiveGate(scorecard=scorecard, human_approved=True)
    assert not gate.allowed
    assert any("记分卡未全绿" in b for b in gate.blockers())
