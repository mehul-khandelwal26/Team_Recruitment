"""In-memory storage for scoring evaluation runs.

Enables historical reproducibility and audit logging. Scoring runs capture:
- Run ID and execution timestamp
- Configuration ID and immutable version used
- Complete team scores and criteria breakdowns
- Associated eligibility statuses (if supplied)
"""

from __future__ import annotations

from typing import Optional, Protocol

from app.scoring.schemas import ScoringRunResponse


class ScoringRunStoreProtocol(Protocol):
    """Protocol for scoring run persistence."""

    def save(self, record: ScoringRunResponse) -> None: ...
    def get(self, run_id: str) -> Optional[ScoringRunResponse]: ...
    def list_runs(self, config_id: Optional[str] = None) -> list[ScoringRunResponse]: ...
    def delete(self, run_id: str) -> bool: ...
    def reset(self) -> None: ...


class InMemoryScoringRunStore:
    """Thread-safe in-memory store for scoring runs."""

    def __init__(self) -> None:
        self._runs: dict[str, ScoringRunResponse] = {}

    def save(self, record: ScoringRunResponse) -> None:
        self._runs[record.run_id] = record.model_copy(deep=True)

    def get(self, run_id: str) -> Optional[ScoringRunResponse]:
        record = self._runs.get(run_id)
        if record is None:
            return None
        return record.model_copy(deep=True)

    def list_runs(self, config_id: Optional[str] = None) -> list[ScoringRunResponse]:
        runs = list(self._runs.values())
        if config_id:
            runs = [r for r in runs if r.config_id == config_id]
        return [r.model_copy(deep=True) for r in runs]

    def delete(self, run_id: str) -> bool:
        """Delete scoring run by run_id."""
        if run_id in self._runs:
            del self._runs[run_id]
            return True
        return False

    def reset(self) -> None:
        self._runs.clear()


from app.storage import DelegatingScoringRunStore

default_scoring_run_store = DelegatingScoringRunStore()
