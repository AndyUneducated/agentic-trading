"""领域错误类型层次。

统一异常基类 `AtradingError`，便于按类型分类处理/告警/安全降级，而非到处 `except
Exception` + 字符串。各层抛出对应子类；主循环捕获时可据类型决定降级策略与指标标签。
"""

from __future__ import annotations


class AtradingError(Exception):
    """本项目所有领域异常的基类。"""


class ConfigError(AtradingError):
    """配置缺失/非法/不一致。"""


class DataError(AtradingError):
    """数据缺失/损坏/违反 PIT 约束。"""


class SignalError(AtradingError):
    """信号层错误（LLM 调用/解析/预算/网关）。"""


class RiskError(AtradingError):
    """风控相关错误（区别于"正常拒单"，指风控本身不可用/被违规绕过）。"""


class BrokerError(AtradingError):
    """券商/执行通道错误（下单失败、连接、状态不一致）。"""


class ExecutionError(AtradingError):
    """执行闭环编排错误。"""


__all__ = [
    "AtradingError",
    "BrokerError",
    "ConfigError",
    "DataError",
    "ExecutionError",
    "RiskError",
    "SignalError",
]
