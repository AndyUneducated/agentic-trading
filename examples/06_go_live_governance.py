"""示例 06：上线治理（记分卡 + 三重红线闸门 + 放量/回滚 + 防篡改审计）。

uv run python examples/06_go_live_governance.py
"""

from __future__ import annotations

from datetime import UTC, datetime

from atrading.core.falsification import EdgeCriteria
from atrading.eval import GoLiveScorecard
from atrading.governance import AuditTrail, CapitalRampController, GoLiveGate


def main() -> None:
    edge = EdgeCriteria(
        beats_zero_baseline=True,
        beats_price_only=True,
        beats_buy_hold=True,
        beats_oss_baseline=True,
        significance_ok=True,
    )
    scorecard = GoLiveScorecard(
        edge=edge,
        oos_metrics_pass=True,
        dsr_pass=True,
        pbo_pass=True,
        net_of_all_costs_positive=True,
        drift_within_bounds=True,
        guardrails_verified=True,
    )

    gate = GoLiveGate(scorecard=scorecard, human_approved=False)  # 三重红线，缺省不放行
    print(f"记分卡通过={scorecard.go} | 允许上线={gate.allowed}")
    print("拦截原因:", gate.blockers())

    ramp = CapitalRampController()  # paper → pilot → ramp → scaled
    decision = ramp.evaluate(
        scorecard_go=scorecard.go, live_drawdown=0.0, drift_ok=True, days_at_stage=5
    )
    print(f"放量决策: {decision.action} → {decision.to_stage}")

    trail = AuditTrail()  # 哈希链防篡改留痕
    trail.append("signal", {"symbol": "AAA", "sentiment": 0.8}, ts=datetime(2026, 1, 1, tzinfo=UTC))
    trail.append("decision", {"symbol": "AAA", "weight": 0.5}, ts=datetime(2026, 1, 1, tzinfo=UTC))
    print("审计链完整:", trail.verify())


if __name__ == "__main__":
    main()
