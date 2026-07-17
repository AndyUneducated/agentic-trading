"""示例 05：防过拟合（walk-forward + DSR + PBO + 留出集守卫）。

uv run python examples/05_anti_overfitting.py
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from atrading.eval import (
    DateRange,
    HoldoutGuard,
    deflated_sharpe_ratio,
    pbo,
    walk_forward,
)


def main() -> None:
    splits = walk_forward(
        start=datetime(2020, 1, 1, tzinfo=UTC),
        end=datetime(2024, 1, 1, tzinfo=UTC),
        train_span=timedelta(days=365),
        test_span=timedelta(days=90),
        step=timedelta(days=90),
    )
    print(f"walk-forward: {len(splits)} 个滚动窗口（测试窗恒在训练窗之后，无未来）")

    dsr = deflated_sharpe_ratio(observed_sharpe=0.12, n_trials=50, n_obs=750)
    print(f"DSR（试 50 组参数后校正）= {dsr:.3f}")
    print(f"PBO（过拟合概率）= {pbo([0.1, 0.2, 0.9], [0.8, 0.3, 0.95]):.2f}")

    guard = HoldoutGuard(
        DateRange(start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2025, 1, 1, tzinfo=UTC))
    )
    guard.acquire("final_eval", note="最终一次性判定")
    print("留出集已一次性取用；再次访问会抛错（防偷看后调参）:", guard.used)


if __name__ == "__main__":
    main()
