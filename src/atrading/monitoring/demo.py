"""最小可运行的 /metrics 端点演示（M9）。

离线、零依赖：填充若干示例指标并在 :9108 暴露 Prometheus 文本格式，便于验证
容器与采集链路。生产中改由 TradingLoop/SentimentExtractor 实时埋点。

运行： uv run python -m atrading.monitoring.demo
"""

from __future__ import annotations

from atrading.monitoring.metrics import MetricsRegistry, build_metrics_server


def main(*, host: str = "0.0.0.0", port: int = 9108) -> None:  # pragma: no cover - 手动运行
    registry = MetricsRegistry()
    registry.describe("atrading_steps_total", "trading loop steps")
    registry.inc("atrading_steps_total", result="ok")
    registry.observe("atrading_decision_seconds", 0.01)

    server = build_metrics_server(registry, host=host, port=port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":  # pragma: no cover - 手动运行
    main()
