"""告警规则（M9）：把度量阈值化为可判定的告警，对齐事件手册。

离线可评估（无需真实 Alertmanager）：给定 MetricsRegistry 与一组规则，返回触发的告警。
真实基建阶段可把同一批阈值翻译为 Prometheus/Alertmanager 规则。
"""

from __future__ import annotations

import operator
from collections.abc import Callable, Sequence
from typing import Literal

from pydantic import BaseModel, Field

from atrading.monitoring.metrics import MetricsRegistry

_OPS: dict[str, Callable[[float, float], bool]] = {
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
    "==": operator.eq,
}

Severity = Literal["warning", "critical"]


class Alert(BaseModel):
    name: str
    severity: Severity
    value: float
    threshold: float
    message: str


class AlertRule(BaseModel):
    name: str
    metric: str
    op: Literal[">", ">=", "<", "<=", "=="]
    threshold: float
    severity: Severity = "warning"
    metric_kind: Literal["counter", "gauge"] = "counter"
    labels: dict[str, str] = Field(default_factory=dict)
    message: str = ""

    def _value(self, registry: MetricsRegistry) -> float | None:
        if self.metric_kind == "gauge":
            return registry.gauge_value(self.metric, **self.labels)
        if self.labels:
            return registry.counter_value(self.metric, **self.labels)
        return registry.counter_total(self.metric)  # 无 label → 跨组合合计

    def evaluate(self, registry: MetricsRegistry) -> Alert | None:
        value = self._value(registry)
        if value is None:  # gauge 从未设置 → 无数据不告警
            return None
        if not _OPS[self.op](value, self.threshold):
            return None
        return Alert(
            name=self.name,
            severity=self.severity,
            value=value,
            threshold=self.threshold,
            message=self.message or f"{self.metric} {self.op} {self.threshold}",
        )


def evaluate_alerts(registry: MetricsRegistry, rules: Sequence[AlertRule]) -> list[Alert]:
    return [alert for rule in rules if (alert := rule.evaluate(registry)) is not None]


def default_rules(*, daily_cost_limit_usd: float | None = None) -> list[AlertRule]:
    """与 runbooks/incident-playbook 对齐的默认告警集。"""
    rules = [
        AlertRule(
            name="ReconcileMismatch",
            metric="atrading_reconcile_mismatch",
            metric_kind="gauge",
            op=">",
            threshold=0.0,
            severity="critical",
            message="内部持仓/成交与券商对账不一致——排查漏单/重复成交，必要时熔断",
        ),
        AlertRule(
            name="DegradedSteps",
            metric="atrading_steps_total",
            labels={"result": "degraded"},
            op=">",
            threshold=0.0,
            severity="warning",
            message="交易循环发生安全降级（默认不交易）——检查数据源/依赖",
        ),
        AlertRule(
            name="SuspiciousDocuments",
            metric="atrading_suspicious_docs_total",
            op=">",
            threshold=0.0,
            severity="warning",
            message="检出疑似 prompt 注入文档——已隔离，复核信号来源",
        ),
    ]
    if daily_cost_limit_usd is not None:
        rules.append(
            AlertRule(
                name="LLMCostBudget",
                metric="atrading_llm_cost_usd_total",
                op=">=",
                threshold=daily_cost_limit_usd,
                severity="critical",
                message="LLM 成本达预算上限——网关应已熔断，核对便宜后端/节流",
            )
        )
    return rules
