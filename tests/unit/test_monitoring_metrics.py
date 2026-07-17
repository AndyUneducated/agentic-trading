from __future__ import annotations

import threading
import urllib.error
import urllib.request

import pytest

from atrading.monitoring.metrics import (
    PROMETHEUS_CONTENT_TYPE,
    MetricsRegistry,
    build_metrics_server,
)


def test_counter_accumulates_and_labels_separate() -> None:
    reg = MetricsRegistry()
    reg.inc("atrading_steps_total", result="ok")
    reg.inc("atrading_steps_total", result="ok")
    reg.inc("atrading_steps_total", result="degraded")

    assert reg.counter_value("atrading_steps_total", result="ok") == 2
    assert reg.counter_value("atrading_steps_total", result="degraded") == 1
    assert reg.counter_value("atrading_steps_total", result="missing") == 0


def test_gauge_overwrites() -> None:
    reg = MetricsRegistry()
    reg.set("atrading_reconcile_mismatch", 3)
    reg.set("atrading_reconcile_mismatch", 0)
    assert reg.gauge_value("atrading_reconcile_mismatch") == 0
    assert reg.gauge_value("atrading_unknown") is None


def test_histogram_observes_sum_and_count() -> None:
    reg = MetricsRegistry()
    reg.observe("atrading_decision_seconds", 0.01)
    reg.observe("atrading_decision_seconds", 0.2)
    total, count = reg.histogram_stats("atrading_decision_seconds")
    assert count == 2
    assert total == pytest.approx(0.21)


def test_render_prometheus_text_format() -> None:
    reg = MetricsRegistry()
    reg.describe("atrading_steps_total", "loop steps")
    reg.inc("atrading_steps_total", result="ok")
    reg.set("atrading_reconcile_mismatch", 0)
    reg.observe("atrading_decision_seconds", 0.03)

    text = reg.render()
    assert "# HELP atrading_steps_total loop steps" in text
    assert "# TYPE atrading_steps_total counter" in text
    assert 'atrading_steps_total{result="ok"} 1' in text
    assert "# TYPE atrading_reconcile_mismatch gauge" in text
    assert "# TYPE atrading_decision_seconds histogram" in text
    assert 'atrading_decision_seconds_bucket{le="+Inf"} 1' in text
    assert "atrading_decision_seconds_count 1" in text
    for line in text.splitlines():
        assert line.startswith("#") or " " in line


def test_label_values_are_escaped() -> None:
    reg = MetricsRegistry()
    reg.inc("atrading_risk_denials_total", reason='bad "quote"')
    assert r'reason="bad \"quote\""' in reg.render()


def test_empty_registry_renders_empty() -> None:
    assert MetricsRegistry().render() == ""


def test_metrics_http_endpoint_serves_exposition() -> None:
    reg = MetricsRegistry()
    reg.inc("atrading_steps_total", result="ok")
    server = build_metrics_server(reg, host="127.0.0.1", port=0)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics", timeout=5) as resp:
            status = resp.status
            content_type = resp.headers.get("Content-Type")
            body = resp.read().decode("utf-8")
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert status == 200
    assert content_type == PROMETHEUS_CONTENT_TYPE
    assert 'atrading_steps_total{result="ok"} 1' in body


def test_metrics_http_endpoint_unknown_path_404() -> None:
    reg = MetricsRegistry()
    server = build_metrics_server(reg, host="127.0.0.1", port=0)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/nope", timeout=5)
            raised = 0
        except urllib.error.HTTPError as exc:
            raised = exc.code
    finally:
        server.shutdown()
        thread.join(timeout=5)
    assert raised == 404
