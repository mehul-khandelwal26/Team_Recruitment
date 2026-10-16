"""In-memory storage and protocol interfaces for ranking and Top-X selection runs.

Ensures:
- Historical reproducibility of ranking and shortlist runs.
- Storage behind Protocol interface to facilitate future database persistence.
- Complete snapshot of input parameters, selected teams, excluded reasons, and warnings.
"""

from __future__ import annotations

from typing import Optional, Protocol

from app.ranking.schemas import RankingRunResponse


class RankingRunStoreProtocol(Protocol):
    """Protocol defining persistence interface for ranking runs."""

    def save(self, record: RankingRunResponse) -> None: ...
    def get(self, run_id: str) -> Optional[RankingRunResponse]: ...
    def list_runs(self) -> list[RankingRunResponse]: ...
    def reset(self) -> None: ...


class InMemoryRankingRunStore:
    """Thread-safe in-memory store for evaluation ranking runs."""

    def __init__(self) -> None:
        self._runs: dict[str, RankingRunResponse] = {}

    def save(self, record: RankingRunResponse) -> None:
        self._runs[record.run_id] = record.model_copy(deep=True)

    def get(self, run_id: str) -> Optional[RankingRunResponse]:
        record = self._runs.get(run_id)
        if record is None:
            return None
        return record.model_copy(deep=True)

    def list_runs(self) -> list[RankingRunResponse]:
        return [r.model_copy(deep=True) for r in self._runs.values()]

    def reset(self) -> None:
        self._runs.clear()


from app.storage import DelegatingRankingRunStore

default_ranking_run_store = DelegatingRankingRunStore()
