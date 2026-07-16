from atrading.core.falsification import EdgeCriteria


def test_default_edge_not_confirmed() -> None:
    assert EdgeCriteria().edge_confirmed is False


def test_all_required_true_confirms_edge() -> None:
    criteria = EdgeCriteria(
        beats_zero_baseline=True,
        beats_price_only=True,
        beats_buy_hold=True,
        significance_ok=True,
    )
    assert criteria.edge_confirmed is True


def test_missing_significance_blocks_edge() -> None:
    criteria = EdgeCriteria(
        beats_zero_baseline=True,
        beats_price_only=True,
        beats_buy_hold=True,
        significance_ok=False,
    )
    assert criteria.edge_confirmed is False


def test_oss_baseline_not_required_for_edge_confirmed() -> None:
    criteria = EdgeCriteria(
        beats_zero_baseline=True,
        beats_price_only=True,
        beats_buy_hold=True,
        significance_ok=True,
        beats_oss_baseline=False,
    )
    assert criteria.edge_confirmed is True
