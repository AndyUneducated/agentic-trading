"""Point-in-Time 行情存储（parquet）。

按 (freq, symbol) 分文件持久化 K 线。read_bars 支持 `as_of` 过滤——只返回
ts<=as_of 的 bar，从存储层杜绝未来函数。pandas 仅限于本模块，其余代码只见
类型化的 Bar 对象。
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

import pandas as pd

from atrading.core.types import Bar

_COLUMNS = ["symbol", "ts", "open", "high", "low", "close", "volume"]


class PITStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _path(self, symbol: str, freq: str) -> Path:
        return self.root / "bars" / f"freq={freq}" / f"{symbol}.parquet"

    def write_bars(self, bars: Iterable[Bar], freq: str) -> None:
        rows = [
            {
                "symbol": b.symbol,
                "ts": b.ts,
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume,
            }
            for b in bars
        ]
        if not rows:
            return
        frame = pd.DataFrame(rows, columns=_COLUMNS)
        frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
        for symbol, group in frame.groupby("symbol"):
            path = self._path(str(symbol), freq)
            path.parent.mkdir(parents=True, exist_ok=True)
            group.sort_values("ts").to_parquet(path, index=False)

    def read_bars(
        self,
        symbols: list[str],
        start: datetime,
        end: datetime,
        freq: str,
        as_of: datetime,
    ) -> list[Bar]:
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        as_of_ts = pd.Timestamp(as_of)
        out: list[Bar] = []
        for symbol in symbols:
            path = self._path(symbol, freq)
            if not path.exists():
                continue
            frame = pd.read_parquet(path)
            mask = (
                (frame["ts"] >= start_ts)
                & (frame["ts"] <= end_ts)
                & (frame["ts"] <= as_of_ts)
            )
            for row in frame[mask].itertuples(index=False):
                out.append(
                    Bar(
                        symbol=str(row.symbol),
                        ts=row.ts.to_pydatetime(),
                        open=float(row.open),
                        high=float(row.high),
                        low=float(row.low),
                        close=float(row.close),
                        volume=float(row.volume),
                    )
                )
        out.sort(key=lambda b: (b.symbol, b.ts))
        return out
