"""实验记账与多重检验惩罚。

每跑一次实验/调参计一次 → `n_trials` 自动累加，喂给 DSR/PBO 量化过拟合惩罚。这是
防"偷偷试很多次挑最好看的"的关键机制。可选持久化到 jsonl，跨会话累加。
"""

from __future__ import annotations

from pathlib import Path

from atrading.experiments.runner import ExperimentResult


class ExperimentRegistry:
    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path is not None else None
        self._by_strategy: dict[str, list[ExperimentResult]] = {}
        if self._path is not None and self._path.exists():
            self._load()

    def _load(self) -> None:
        assert self._path is not None
        for line in self._path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            result = ExperimentResult.model_validate_json(line)
            self._by_strategy.setdefault(result.strategy, []).append(result)

    def record(self, result: ExperimentResult) -> None:
        self._by_strategy.setdefault(result.strategy, []).append(result)
        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(result.model_dump_json() + "\n")

    def n_trials(self, strategy: str) -> int:
        return len(self._by_strategy.get(strategy, []))

    def results(self, strategy: str) -> list[ExperimentResult]:
        return list(self._by_strategy.get(strategy, []))
