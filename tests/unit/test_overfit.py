from __future__ import annotations

import pytest

from atrading.eval import deflated_sharpe_ratio, expected_max_sharpe, pbo


def test_expected_max_sharpe_grows_with_trials() -> None:
    assert expected_max_sharpe(1) == 0.0
    assert expected_max_sharpe(100) > expected_max_sharpe(10) > 0.0


def test_dsr_penalizes_more_trials() -> None:
    few = deflated_sharpe_ratio(0.2, n_trials=1, n_obs=252)
    many = deflated_sharpe_ratio(0.2, n_trials=1000, n_obs=252)
    assert 0.0 <= many < few <= 1.0


def test_dsr_rewards_more_observations() -> None:
    short = deflated_sharpe_ratio(0.15, n_trials=10, n_obs=60)
    long = deflated_sharpe_ratio(0.15, n_trials=10, n_obs=500)
    assert long > short


def test_pbo_extremes() -> None:
    is_ranks = [0.1, 0.2, 0.3, 0.4]
    oos_bad = [0.9, 0.8, 0.7, 0.6]  # 样本内好、样本外差 → 全翻车
    oos_good = [0.1, 0.2, 0.3, 0.4]  # 保持 → 不翻车
    assert pbo(is_ranks, oos_bad) == pytest.approx(1.0)
    assert pbo(is_ranks, oos_good) == pytest.approx(0.0)
