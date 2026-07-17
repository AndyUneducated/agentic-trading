"""示例 04：信号质量评测（IC / 显著性 / 保守偏差）。

盈利之外**独立**衡量信号预测力——信号级裁判，避免"复述已定价信息"。

    uv run python examples/04_signal_eval.py
"""

from __future__ import annotations

from atrading.eval import check_conservatism, evaluate_signal


def main() -> None:
    sentiments = [0.8, -0.6, 0.4, -0.9, 0.2, 0.5, -0.3]
    forward_returns = [0.03, -0.02, 0.01, -0.04, 0.015, 0.02, -0.01]  # 须严格取自各 as_of 之后

    ev = evaluate_signal(sentiments, forward_returns)
    print(f"IC={ev.ic:.3f} rankIC={ev.rank_ic:.3f} 命中率={ev.hit_rate:.0%}")
    print(f"IC t 统计={ev.ic_t_stat:.2f} 显著(|t|>=2)={ev.is_significant()}")

    cons = check_conservatism(sentiments)
    print(f"均值情绪={cons.mean_sentiment:+.2f} 看空占比={cons.frac_negative:.0%}")
    print(f"保守偏差={cons.biased}")


if __name__ == "__main__":
    main()
