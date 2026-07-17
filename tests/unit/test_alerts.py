from __future__ import annotations

from atrading.monitoring.alerts import AlertRule, default_rules, evaluate_alerts
from atrading.monitoring.metrics import MetricsRegistry


def test_gauge_rule_fires_above_threshold() -> None:
    registry = MetricsRegistry()
    registry.set("atrading_reconcile_mismatch", 1.0)
    alerts = evaluate_alerts(registry, default_rules())
    names = {a.name for a in alerts}
    assert "ReconcileMismatch" in names
    critical = next(a for a in alerts if a.name == "ReconcileMismatch")
    assert critical.severity == "critical"


def test_no_alert_when_clean() -> None:
    registry = MetricsRegistry()
    registry.set("atrading_reconcile_mismatch", 0.0)
    assert evaluate_alerts(registry, default_rules()) == []


def test_labeled_counter_rule() -> None:
    registry = MetricsRegistry()
    registry.inc("atrading_steps_total", result="ok")
    registry.inc("atrading_steps_total", result="degraded")
    alerts = evaluate_alerts(registry, default_rules())
    assert any(a.name == "DegradedSteps" for a in alerts)


def test_counter_total_sums_labels() -> None:
    registry = MetricsRegistry()
    registry.inc("atrading_llm_cost_usd_total", 0.6, model="a")
    registry.inc("atrading_llm_cost_usd_total", 0.6, model="b")
    rules = default_rules(daily_cost_limit_usd=1.0)
    alerts = evaluate_alerts(registry, rules)
    assert any(a.name == "LLMCostBudget" for a in alerts)  # 0.6+0.6=1.2 >= 1.0


def test_missing_gauge_does_not_fire() -> None:
    registry = MetricsRegistry()
    rule = AlertRule(name="X", metric="never_set", metric_kind="gauge", op=">", threshold=0.0)
    assert evaluate_alerts(registry, [rule]) == []
