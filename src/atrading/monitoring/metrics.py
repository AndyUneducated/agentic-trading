"""零依赖度量指标（M9 可观测性）。

实现 Counter / Gauge / Histogram，并按 **Prometheus 文本 exposition 格式**导出，
可被真实 Prometheus 直接 scrape。`prometheus_client` / OpenTelemetry 作为后续可选
升级；本机算力有限，核心不引入重依赖。

设计约束：
- 埋点默认可选（构造方传入 `MetricsRegistry | None`，`None` = 不埋点），不改决策逻辑。
- 纯累加/覆盖，确定性可断言（便于测试）。
- 线程安全（单进程主循环足够，但保留 Lock 以防未来并发采集）。
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Lock

_LabelKey = tuple[tuple[str, str], ...]

DEFAULT_BUCKETS: tuple[float, ...] = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
)

PROMETHEUS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


def _label_key(labels: dict[str, str]) -> _LabelKey:
    return tuple(sorted(labels.items()))


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _format_labels(labels: _LabelKey, extra: tuple[tuple[str, str], ...] = ()) -> str:
    items = [*labels, *extra]
    if not items:
        return ""
    inner = ",".join(f'{key}="{_escape(val)}"' for key, val in items)
    return "{" + inner + "}"


def _num(value: float) -> str:
    if value == int(value) and abs(value) < 1e15:
        return str(int(value))
    return repr(value)


class _Histogram:
    __slots__ = ("bounds", "count", "counts", "sum")

    def __init__(self, bounds: tuple[float, ...]) -> None:
        self.bounds = bounds
        self.counts = [0] * len(bounds)  # 落入"最小的 bound >= value"的桶（非累积）
        self.sum = 0.0
        self.count = 0

    def observe(self, value: float) -> None:
        self.sum += value
        self.count += 1
        for index, bound in enumerate(self.bounds):
            if value <= bound:
                self.counts[index] += 1
                break


class MetricsRegistry:
    """轻量指标注册表：Counter/Gauge/Histogram + Prometheus 文本导出。"""

    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: dict[str, dict[_LabelKey, float]] = {}
        self._gauges: dict[str, dict[_LabelKey, float]] = {}
        self._histograms: dict[str, dict[_LabelKey, _Histogram]] = {}
        self._help: dict[str, str] = {}
        self._buckets: dict[str, tuple[float, ...]] = {}

    def describe(self, name: str, help_text: str) -> None:
        with self._lock:
            self._help[name] = help_text

    def register_histogram(self, name: str, buckets: tuple[float, ...]) -> None:
        with self._lock:
            self._buckets[name] = tuple(sorted(buckets))

    def inc(self, name: str, value: float = 1.0, **labels: str) -> None:
        key = _label_key(labels)
        with self._lock:
            series = self._counters.setdefault(name, {})
            series[key] = series.get(key, 0.0) + value

    def set(self, name: str, value: float, **labels: str) -> None:
        key = _label_key(labels)
        with self._lock:
            self._gauges.setdefault(name, {})[key] = value

    def observe(self, name: str, value: float, **labels: str) -> None:
        key = _label_key(labels)
        with self._lock:
            series = self._histograms.setdefault(name, {})
            hist = series.get(key)
            if hist is None:
                hist = _Histogram(self._buckets.get(name, DEFAULT_BUCKETS))
                series[key] = hist
            hist.observe(value)

    def counter_value(self, name: str, **labels: str) -> float:
        with self._lock:
            return self._counters.get(name, {}).get(_label_key(labels), 0.0)

    def gauge_value(self, name: str, **labels: str) -> float | None:
        with self._lock:
            return self._gauges.get(name, {}).get(_label_key(labels))

    def histogram_stats(self, name: str, **labels: str) -> tuple[float, int]:
        with self._lock:
            hist = self._histograms.get(name, {}).get(_label_key(labels))
            return (0.0, 0) if hist is None else (hist.sum, hist.count)

    def _header(self, lines: list[str], name: str, metric_type: str) -> None:
        if name in self._help:
            lines.append(f"# HELP {name} {self._help[name]}")
        lines.append(f"# TYPE {name} {metric_type}")

    def render(self) -> str:
        """输出 Prometheus 文本 exposition 格式。"""
        lines: list[str] = []
        with self._lock:
            for name in sorted(self._counters):
                self._header(lines, name, "counter")
                for key, value in sorted(self._counters[name].items(), key=lambda kv: kv[0]):
                    lines.append(f"{name}{_format_labels(key)} {_num(value)}")
            for name in sorted(self._gauges):
                self._header(lines, name, "gauge")
                for key, value in sorted(self._gauges[name].items(), key=lambda kv: kv[0]):
                    lines.append(f"{name}{_format_labels(key)} {_num(value)}")
            for name in sorted(self._histograms):
                self._header(lines, name, "histogram")
                for key, hist in sorted(self._histograms[name].items(), key=lambda kv: kv[0]):
                    cumulative = 0
                    for index, bound in enumerate(hist.bounds):
                        cumulative += hist.counts[index]
                        le = (("le", repr(bound)),)
                        lines.append(f"{name}_bucket{_format_labels(key, le)} {cumulative}")
                    inf = (("le", "+Inf"),)
                    lines.append(f"{name}_bucket{_format_labels(key, inf)} {hist.count}")
                    lines.append(f"{name}_sum{_format_labels(key)} {_num(hist.sum)}")
                    lines.append(f"{name}_count{_format_labels(key)} {hist.count}")
        return "\n".join(lines) + "\n" if lines else ""


def _make_handler(registry: MetricsRegistry) -> type[BaseHTTPRequestHandler]:
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path.rstrip("/") not in ("", "/metrics"):
                self.send_response(404)
                self.end_headers()
                return
            body = registry.render().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", PROMETHEUS_CONTENT_TYPE)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return  # 静默，避免污染日志

    return _Handler


def build_metrics_server(
    registry: MetricsRegistry, *, host: str = "0.0.0.0", port: int = 9108
) -> HTTPServer:
    """构造暴露 `/metrics` 的 HTTP server（供容器/进程内采集）。

    调用方负责 `serve_forever()` 与 `shutdown()`。绑定端口 0 可获系统分配端口（测试用）。
    """
    return HTTPServer((host, port), _make_handler(registry))
