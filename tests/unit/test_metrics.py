from __future__ import annotations

import pytest

from atrading.eval import max_drawdown, returns_from_equity, sharpe, total_return


def test_returns_from_equity() -> None:
    assert returns_from_equity([100.0, 110.0, 121.0]) == pytest.approx([0.1, 0.1])


def test_total_return() -> None:
    assert total_return([100.0, 121.0]) == pytest.approx(0.21)
    assert total_return([100.0]) == 0.0


def test_max_drawdown() -> None:
    assert max_drawdown([100.0, 110.0, 121.0]) == pytest.approx(0.0)
    assert max_drawdown([100.0, 80.0, 120.0]) == pytest.approx(0.2)


def test_sharpe_zero_when_insufficient_or_flat() -> None:
    assert sharpe([]) == 0.0
    assert sharpe([0.01]) == 0.0
    assert sharpe([0.01, 0.01, 0.01]) == 0.0


def test_sharpe_positive_for_positive_mean() -> None:
    assert sharpe([0.02, -0.01, 0.03, 0.01]) > 0.0
