"""atrading 命令行入口。

子命令：
  version   打印版本
  gate      打印/校验安全护栏姿态（trading_mode / kill_switch / can_trade）
  backtest  在（默认合成、离线可跑的）行情上跑确定性回测并打印指标

设计原则：CLI 只做"编排 + 展示"，不含任何决策/风控逻辑——完全复用 `src` 内的确定性
组件，保证 CLI 与库行为一致（回测-实盘同源的延伸）。合成数据仅用于烟囱测试与演示，
**不构成任何真实 alpha 证据**（真实数据/实证见 docs/experiments/）。
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from importlib import metadata
from pathlib import Path

from atrading.app import build_backtest, build_paper_loop
from atrading.backtest import CostModel
from atrading.config import RunConfig, Settings
from atrading.core.signal_schema import SignalSchemaV1
from atrading.core.strategy_config import StrategyConfig
from atrading.core.types import Bar
from atrading.data import InMemoryDataSource
from atrading.eval import max_drawdown, returns_from_equity, sharpe, total_return
from atrading.execution import SimulatedBroker, SQLiteStateStore
from atrading.logging_config import configure_logging, get_logger
from atrading.registry import available_policies
from atrading.signals import LLMSignalSource


def _version() -> str:
    try:
        return metadata.version("atrading")
    except metadata.PackageNotFoundError:
        return "0.0.0+dev"


def synthetic_bars(universe: list[str], *, days: int, seed: int) -> list[Bar]:
    """确定性合成日线（种子化几何游走）。仅供离线演示/烟囱测试。"""
    rng = random.Random(seed)
    start = datetime(2024, 1, 1, tzinfo=UTC)
    bars: list[Bar] = []
    for i, symbol in enumerate(universe):
        price = 100.0 * (1.0 + 0.1 * i)
        for day in range(days):
            price = max(1.0, price * (1.0 + 0.0003 + rng.gauss(0.0, 0.01)))
            ts = start + timedelta(days=day)
            bar = Bar(
                symbol=symbol, ts=ts, open=price, high=price, low=price, close=price, volume=1.0
            )
            bars.append(bar)
    return bars


def _cmd_version(_args: argparse.Namespace) -> int:
    print(f"atrading {_version()}")
    return 0


def _cmd_gate(args: argparse.Namespace) -> int:
    settings = Settings()
    posture = {
        "trading_mode": settings.trading_mode,
        "kill_switch": settings.kill_switch,
        "can_trade": settings.can_trade,
    }
    if args.json:
        print(json.dumps(posture))
        return 0
    print(f"trading_mode = {settings.trading_mode}")
    print(f"kill_switch  = {settings.kill_switch}")
    print(f"can_trade    = {settings.can_trade}")
    if not settings.can_trade:
        print("[warn] 当前不可下单（kill switch 开启或 live 未确认）——安全默认。")
    return 0


def _cmd_backtest(args: argparse.Namespace) -> int:
    log = get_logger()
    if args.config:
        config = StrategyConfig.from_yaml(args.config)
    else:
        config = StrategyConfig(name="demo", universe=["AAA", "BBB", "CCC"], decision_freq="daily")

    bars = synthetic_bars(config.universe, days=args.days, seed=args.seed)
    runner = build_backtest(
        config=config,
        data=InMemoryDataSource(bars),
        costs=CostModel(commission_bps=1.0, slippage_bps=5.0),
        policy=args.policy,
        seed=args.seed,
    )
    result = runner.run(bars[0].ts, bars[-1].ts)

    equity = result.equity_values()
    rets = returns_from_equity(equity)
    tr = total_return(equity)
    mdd = max_drawdown(equity)
    shp = sharpe(rets)

    log.info(
        "backtest_done",
        strategy=config.name,
        periods=len(equity),
        total_return=round(tr, 4),
        max_drawdown=round(mdd, 4),
        sharpe=round(shp, 3),
    )
    if args.json:
        print(
            json.dumps(
                {
                    "strategy": config.name,
                    "universe": config.universe,
                    "periods": len(equity),
                    "final_equity": round(result.final_equity, 2),
                    "total_return": round(tr, 4),
                    "max_drawdown": round(mdd, 4),
                    "sharpe": round(shp, 3),
                }
            )
        )
        return 0
    print(f"策略 {config.name}({args.policy}) 标的 {len(config.universe)} 周期 {len(equity)}")
    print(f"总收益 {tr:+.2%}  最大回撤 {mdd:.2%}  Sharpe {shp:.3f}")
    print("[note] 合成数据仅供烟囱测试，非真实 alpha 证据（真实实证见 docs/experiments/）。")
    return 0


def _cmd_paper(args: argparse.Namespace) -> int:
    log = get_logger()
    run_config = RunConfig.from_yaml(args.config)
    strategy = run_config.load_strategy()
    settings = Settings()

    bars = synthetic_bars(strategy.universe, days=args.days, seed=args.seed)
    prices: dict[str, float] = {}
    first_day = bars[0].ts
    # 合成一条正面信号（每标的，as_of 首日）驱动闭环产生交易——仅演示。
    signals = LLMSignalSource(
        [
            SignalSchemaV1(
                symbol=symbol,
                as_of=first_day,
                sentiment=0.5,
                horizon_days=5,
                confidence=0.9,
                model_version="offline-demo",
                prompt_version="v1",
                rationale="demo",
            )
            for symbol in strategy.universe
        ]
    )
    timestamps = sorted({bar.ts for bar in bars})
    with tempfile.TemporaryDirectory() as tmp:
        loop = build_paper_loop(
            run_config=run_config,
            settings=settings,
            data=InMemoryDataSource(bars),
            prices=prices,
            state_store=SQLiteStateStore(Path(tmp) / "state.db", namespace=strategy.name),
            broker=SimulatedBroker(prices),
            signals=signals,
        )
        reports = loop.run(timestamps)

    submitted = sum(len(report.submitted_order_ids) for report in reports)
    denied = sum(len(report.denied) for report in reports)
    degraded = sum(1 for report in reports if report.degraded)
    log.info(
        "paper_done",
        strategy=strategy.name,
        steps=len(reports),
        submitted=submitted,
        denied=denied,
        degraded=degraded,
    )
    if args.json:
        print(
            json.dumps(
                {
                    "strategy": strategy.name,
                    "steps": len(reports),
                    "submitted": submitted,
                    "denied": denied,
                    "degraded": degraded,
                    "final_positions": loop.state.positions,
                }
            )
        )
        return 0
    print(f"策略: {strategy.name}  标的数: {len(strategy.universe)}  步数: {len(reports)}")
    print(f"提交订单: {submitted}  风控拒单: {denied}  安全降级步: {degraded}")
    print(f"最终持仓标的数: {len(loop.state.positions)}")
    print("[note] 合成数据 + 模拟 broker，演示 config 驱动的完整闭环，非真实 alpha/实盘。")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="atrading", description="Agentic trading — 混合架构交易研究系统 CLI"
    )
    parser.add_argument("--log-format", choices=["json", "console"], default="console")
    sub = parser.add_subparsers(dest="command", required=True)

    p_version = sub.add_parser("version", help="打印版本")
    p_version.set_defaults(func=_cmd_version)

    p_gate = sub.add_parser("gate", help="打印/校验安全护栏姿态")
    p_gate.add_argument("--json", action="store_true", help="以 JSON 输出")
    p_gate.set_defaults(func=_cmd_gate)

    p_bt = sub.add_parser("backtest", help="在合成/配置行情上跑确定性回测")
    p_bt.add_argument("--config", help="StrategyConfig YAML 路径（默认内置 demo）")
    p_bt.add_argument(
        "--policy", default="equal_weight", choices=available_policies(), help="决策策略名"
    )
    p_bt.add_argument("--days", type=int, default=180, help="合成天数")
    p_bt.add_argument("--seed", type=int, default=7, help="随机种子（可复现）")
    p_bt.add_argument("--json", action="store_true", help="以 JSON 输出")
    p_bt.set_defaults(func=_cmd_backtest)

    p_paper = sub.add_parser("paper", help="从 RunConfig 装配完整模拟盘闭环（合成数据离线跑）")
    p_paper.add_argument("--config", default="configs/paper.yaml", help="RunConfig YAML 路径")
    p_paper.add_argument("--days", type=int, default=30, help="合成天数")
    p_paper.add_argument("--seed", type=int, default=7, help="随机种子（可复现）")
    p_paper.add_argument("--json", action="store_true", help="以 JSON 输出")
    p_paper.set_defaults(func=_cmd_paper)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(fmt=args.log_format)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
