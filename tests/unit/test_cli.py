from __future__ import annotations

import json

import pytest

from atrading.cli import main, synthetic_bars


def _last_json(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]
    return json.loads(lines[-1])  # type: ignore[no-any-return]


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["version"]) == 0
    assert "atrading" in capsys.readouterr().out


def test_gate_json_defaults_paper(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["gate", "--json"]) == 0
    data = _last_json(capsys)
    assert data["trading_mode"] == "paper"
    assert data["can_trade"] is True


def test_backtest_json_and_reproducible(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["backtest", "--days", "60", "--seed", "3", "--json"]) == 0
    first = _last_json(capsys)
    assert first["periods"] == 60
    assert first["strategy"] == "demo"

    assert main(["backtest", "--days", "60", "--seed", "3", "--json"]) == 0
    assert _last_json(capsys) == first  # 同种子 → 完全可复现


def test_synthetic_bars_seed_reproducible() -> None:
    a = synthetic_bars(["X", "Y"], days=10, seed=1)
    b = synthetic_bars(["X", "Y"], days=10, seed=1)
    assert [bar.close for bar in a] == [bar.close for bar in b]
    assert len(a) == 20


def test_missing_subcommand_errors() -> None:
    with pytest.raises(SystemExit):
        main([])
