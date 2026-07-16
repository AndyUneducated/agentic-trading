"""证伪判定与 go-live 记分卡。

CharterThresholds 是成功指标的单一数据源（对齐 PROJECT_CHARTER；具体数值 M0 定稿，
此处给出符合行业惯例的默认值）。build_edge_criteria 依据策略 vs 多基线的对比填充
EdgeCriteria；GoLiveScorecard 汇总所有硬门槛，全绿才建议进入上线闸门评审。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from atrading.backtest.runner import BacktestResult
from atrading.core.falsification import EdgeCriteria
from atrading.eval.metrics import excess_return, max_drawdown, sharpe
from atrading.eval.signal_eval import SignalEvalResult


class CharterThresholds(BaseModel):
    """成功指标门槛（默认值为行业惯例草案，待 CHARTER/M0 定稿覆盖）。"""

    max_drawdown_limit: float = 0.20  # 硬约束：回撤 < 20%
    min_sharpe: float = 1.0  # Sharpe 下限
    min_excess_return: float = 0.0  # 相对基准超额需为正
    min_dsr: float = 0.95  # Deflated Sharpe 概率门槛
    max_pbo: float = 0.5  # 过拟合概率上限
    signal_ic_t_stat: float = 2.0  # 信号显著性 t 门槛


def build_edge_criteria(
    *,
    strategy: BacktestResult,
    baselines: dict[str, BacktestResult],
    signal: SignalEvalResult | None = None,
    thresholds: CharterThresholds | None = None,
    oss_baseline: BacktestResult | None = None,
) -> EdgeCriteria:
    """依据策略权益 vs 各基线权益，填充 Edge 证伪四项 + 显著性。"""
    thresholds = thresholds or CharterThresholds()
    strat_equity = strategy.equity_values()

    def beats(name: str) -> bool:
        base = baselines.get(name)
        if base is None:
            return False
        return excess_return(strat_equity, base.equity_values()) > thresholds.min_excess_return

    significance_ok = signal is not None and abs(signal.ic_t_stat) >= thresholds.signal_ic_t_stat

    return EdgeCriteria(
        beats_zero_baseline=beats("zero"),
        beats_price_only=beats("price_only"),
        beats_buy_hold=beats("buy_hold"),
        beats_oss_baseline=(
            oss_baseline is not None
            and excess_return(strat_equity, oss_baseline.equity_values())
            > thresholds.min_excess_return
        ),
        significance_ok=significance_ok,
    )


class GoLiveScorecard(BaseModel):
    edge: EdgeCriteria
    oos_metrics_pass: bool = False
    dsr_pass: bool = False
    pbo_pass: bool = False
    net_of_all_costs_positive: bool = False
    drift_within_bounds: bool = False
    guardrails_verified: bool = False
    notes: list[str] = Field(default_factory=list)

    @property
    def go(self) -> bool:
        return all(
            [
                self.edge.edge_confirmed,
                self.oos_metrics_pass,
                self.dsr_pass,
                self.pbo_pass,
                self.net_of_all_costs_positive,
                self.drift_within_bounds,
                self.guardrails_verified,
            ]
        )


def evaluate_oos_metrics(
    result: BacktestResult,
    thresholds: CharterThresholds | None = None,
    *,
    periods_per_year: int = 252,
) -> bool:
    """样本外权益是否达 CHARTER 指标（回撤上限 + Sharpe 下限）。"""
    thresholds = thresholds or CharterThresholds()
    equity = result.equity_values()
    if len(equity) < 2:
        return False
    rets = [equity[i] / equity[i - 1] - 1.0 for i in range(1, len(equity))]
    dd_ok = max_drawdown(equity) <= thresholds.max_drawdown_limit
    sharpe_ok = sharpe(rets, periods_per_year=periods_per_year) >= thresholds.min_sharpe
    return dd_ok and sharpe_ok
