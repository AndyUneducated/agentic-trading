"""行情数据质量检查。

坏数据会污染回测并伪造 Edge。上线数据前跑这些检查：重复时间戳、
非正价格、非单调时间序列（乱序）。纯 Python，无 IO。
"""

from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel

from atrading.core.types import Bar


class QualityReport(BaseModel):
    n_bars: int
    duplicate_timestamps: int
    non_positive_prices: int
    out_of_order: int

    @property
    def ok(self) -> bool:
        return (
            self.duplicate_timestamps == 0
            and self.non_positive_prices == 0
            and self.out_of_order == 0
        )


def check_bars(bars: list[Bar]) -> QualityReport:
    by_symbol: dict[str, list[Bar]] = defaultdict(list)
    for bar in bars:
        by_symbol[bar.symbol].append(bar)

    duplicates = 0
    non_positive = 0
    out_of_order = 0
    for symbol_bars in by_symbol.values():
        seen: set[object] = set()
        prev_ts = None
        for bar in symbol_bars:
            if bar.ts in seen:
                duplicates += 1
            seen.add(bar.ts)
            if prev_ts is not None and bar.ts < prev_ts:
                out_of_order += 1
            prev_ts = bar.ts
            if min(bar.open, bar.high, bar.low, bar.close) <= 0:
                non_positive += 1

    return QualityReport(
        n_bars=len(bars),
        duplicate_timestamps=duplicates,
        non_positive_prices=non_positive,
        out_of_order=out_of_order,
    )
