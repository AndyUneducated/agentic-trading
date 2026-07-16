from __future__ import annotations

import pytest

from atrading.eval import check_conservatism, evaluate_signal


def test_perfect_positive_ic() -> None:
    signals = [0.1, 0.2, 0.3, 0.4, 0.5]
    returns = [0.01, 0.02, 0.03, 0.04, 0.05]
    result = evaluate_signal(signals, returns)
    assert result.ic == pytest.approx(1.0)
    assert result.rank_ic == pytest.approx(1.0)
    assert result.hit_rate == pytest.approx(1.0)


def test_strong_but_imperfect_ic_is_significant() -> None:
    signals = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
    returns = [0.01, 0.03, 0.02, 0.05, 0.06, 0.08]
    result = evaluate_signal(signals, returns)
    assert result.ic > 0.8
    assert result.hit_rate == pytest.approx(1.0)
    assert result.is_significant()


def test_negative_correlation() -> None:
    signals = [0.5, 0.4, 0.3, 0.2, 0.1]
    returns = [-0.05, -0.04, -0.03, -0.02, -0.01]
    result = evaluate_signal(signals, returns)
    assert result.ic == pytest.approx(-1.0)
    # 信号与收益同号判定：正信号却负收益 → 命中率 0。
    assert result.hit_rate == pytest.approx(0.0)


def test_length_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="长度必须一致"):
        evaluate_signal([0.1, 0.2], [0.1])


def test_hit_rate_ignores_zero_signals() -> None:
    result = evaluate_signal([0.0, 0.5, -0.5], [0.1, 0.1, -0.1])
    # 只有两个非零信号，均命中。
    assert result.hit_rate == pytest.approx(1.0)


def test_conservatism_flags_bearish_bias() -> None:
    biased = check_conservatism([-0.5, -0.6, -0.4, -0.7])
    assert biased.biased
    assert biased.frac_negative == pytest.approx(1.0)

    neutral = check_conservatism([0.2, -0.1, 0.3, 0.0])
    assert not neutral.biased


def test_conservatism_empty() -> None:
    report = check_conservatism([])
    assert report.n == 0
    assert not report.biased
