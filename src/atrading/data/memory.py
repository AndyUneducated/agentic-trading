"""内存行情源（用于测试、合成数据与 golden 回测）。

实现 DataSource 协议。get_bars 仅返回 [start, end] 窗口内的数据；PIT 的逐期切片
由 BacktestRunner 负责（构造 DecisionContext 时只喂 ts<=as_of 的历史）。
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from atrading.core.types import Bar


class InMemoryDataSource:
    def __init__(self, bars: Iterable[Bar]) -> None:
        self._bars = sorted(bars, key=lambda b: (b.symbol, b.ts))

    def get_bars(
        self, symbols: list[str], start: datetime, end: datetime, freq: str
    ) -> list[Bar]:
        wanted = set(symbols)
        return [
            bar
            for bar in self._bars
            if bar.symbol in wanted and start <= bar.ts <= end
        ]
