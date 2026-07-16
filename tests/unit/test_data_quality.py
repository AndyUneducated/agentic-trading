from __future__ import annotations

from datetime import UTC, datetime

from atrading.core.types import Bar
from atrading.data import check_bars


def _bar(symbol: str, day: int, close: float = 1.0) -> Bar:
    ts = datetime(2026, 1, day, tzinfo=UTC)
    return Bar(symbol=symbol, ts=ts, open=close, high=close, low=close, close=close, volume=1)


def test_clean_bars_report_ok() -> None:
    report = check_bars([_bar("A", 1), _bar("A", 2), _bar("A", 3)])
    assert report.ok
    assert report.n_bars == 3


def test_detects_duplicates_and_out_of_order() -> None:
    report = check_bars([_bar("A", 2), _bar("A", 1), _bar("A", 1)])
    assert report.duplicate_timestamps == 1
    assert report.out_of_order == 1
    assert not report.ok


def test_detects_non_positive_price() -> None:
    report = check_bars([_bar("A", 1, close=0.0)])
    assert report.non_positive_prices == 1
    assert not report.ok
