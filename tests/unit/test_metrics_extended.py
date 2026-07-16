from __future__ import annotations

import pytest

from atrading.eval import excess_return, sortino, turnover


def test_sortino_only_penalizes_downside() -> None:
    assert sortino([0.01, 0.01, 0.01]) == 0.0  # 无下行 → 0
    mixed = sortino([0.02, -0.01, 0.03, -0.02, 0.01])
    assert mixed != 0.0


def test_turnover_includes_initial_build() -> None:
    series = [{"A": 0.5, "B": 0.5}, {"A": 0.5, "B": 0.5}, {"A": 1.0}]
    # 首期建仓 1.0；第二期不变 0；第三期 B 0.5→0 + A 0.5→1.0 = 1.0。
    assert turnover(series) == pytest.approx(2.0)


def test_excess_return() -> None:
    assert excess_return([100.0, 130.0], [100.0, 120.0]) == pytest.approx(0.1)
