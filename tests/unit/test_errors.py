from __future__ import annotations

import pytest

from atrading.core.errors import (
    AtradingError,
    BrokerError,
    ConfigError,
    DataError,
    RiskError,
    SignalError,
)
from atrading.signals.budget import BudgetExceededError
from atrading.signals.gateway import GatewayError


def test_all_subclass_base() -> None:
    for cls in (ConfigError, DataError, SignalError, RiskError, BrokerError):
        assert issubclass(cls, AtradingError)


def test_signal_exceptions_join_hierarchy() -> None:
    assert issubclass(GatewayError, SignalError)
    assert issubclass(BudgetExceededError, SignalError)
    assert issubclass(GatewayError, AtradingError)


def test_catch_specific_as_base() -> None:
    with pytest.raises(AtradingError):
        raise GatewayError("boom")
    with pytest.raises(SignalError):
        raise BudgetExceededError("boom")
