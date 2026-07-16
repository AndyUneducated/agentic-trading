import pytest

from atrading.config.settings import Settings

_ENV_KEYS = ["TRADING_MODE", "KILL_SWITCH", "LIVE_CONFIRMED"]


def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_defaults_are_paper_and_can_trade(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.trading_mode == "paper"
    assert settings.kill_switch is False
    assert settings.can_trade is True


def test_live_mode_requires_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    with pytest.raises(ValueError, match="live_confirmed"):
        Settings(_env_file=None, trading_mode="live", live_confirmed=False)  # type: ignore[call-arg]


def test_live_mode_confirmed_can_trade(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    settings = Settings(_env_file=None, trading_mode="live", live_confirmed=True)  # type: ignore[call-arg]
    assert settings.can_trade is True


def test_kill_switch_blocks_trading(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    settings = Settings(_env_file=None, kill_switch=True)  # type: ignore[call-arg]
    assert settings.can_trade is False
