"""时钟实现（core.Clock 协议）。

回测=模拟钟（由外部喂时间戳），实盘=真实钟。把时间源做成可注入的依赖，让
`TradingLoop` 在回测与实盘走同一代码路径，环境差异只体现在注入的 Clock 实现里
（ADR-0003 回测-实盘一致）。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


class SystemClock:
    """真实钟：返回当前 UTC 时间。"""

    def now(self) -> datetime:
        return datetime.now(tz=UTC)


class ManualClock:
    """可控钟：用于测试与回测，时间只在显式推进时前进。"""

    def __init__(self, start: datetime) -> None:
        self._now = start

    def now(self) -> datetime:
        return self._now

    def set(self, ts: datetime) -> None:
        self._now = ts

    def advance(self, delta: timedelta) -> datetime:
        self._now = self._now + delta
        return self._now
