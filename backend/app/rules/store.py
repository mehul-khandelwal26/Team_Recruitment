"""In-memory storage interfaces and implementations for evaluation runs and manual overrides.

Enables clean separation between:
1. Historical evaluation runs (immutable snapshot of calculated decisions).
2. Organizer manual overrides (independent audit log; original runs are never mutated).

Both stores are placed behind small protocols to facilitate future database persistence.
"""

from __future__ import annotations

from typing import Optional, Protocol

from app.rules.schemas import EligibilityRunResponse, ManualOverride


# ---------------------------------------------------------------------------
# Protocols (Interfaces)
# ---------------------------------------------------------------------------


class RunStore(Protocol):
    """Protocol for eligibility run record persistence."""

    def save(self, record: EligibilityRunResponse) -> None: ...
    def get(self, run_id: str) -> Optional[EligibilityRunResponse]: ...
    def list_runs(self, config_id: Optional[str] = None) -> list[EligibilityRunResponse]: ...
    def reset(self) -> None: ...


class OverrideStore(Protocol):
    """Protocol for manual override persistence."""

    def save(self, override: ManualOverride) -> None: ...
    def get_for_run(self, run_id: str) -> list[ManualOverride]: ...
    def get_for_team(self, run_id: str, team_id: str) -> Optional[ManualOverride]: ...
    def reset(self) -> None: ...


# ---------------------------------------------------------------------------
# In-Memory Implementations
# ---------------------------------------------------------------------------


class InMemoryRunStore:
    """Thread-safe in-memory store for evaluation runs."""

    def __init__(self) -> None:
        self._runs: dict[str, EligibilityRunResponse] = {}

    def save(self, record: EligibilityRunResponse) -> None:
        self._runs[record.run_id] = record.model_copy(deep=True)

    def get(self, run_id: str) -> Optional[EligibilityRunResponse]:
        record = self._runs.get(run_id)
        if record is None:
            return None
        return record.model_copy(deep=True)

    def list_runs(self, config_id: Optional[str] = None) -> list[EligibilityRunResponse]:
        runs = list(self._runs.values())
        if config_id:
            runs = [r for r in runs if r.config_id == config_id]
        return [r.model_copy(deep=True) for r in runs]

    def reset(self) -> None:
        self._runs.clear()


class InMemoryOverrideStore:
    """Thread-safe in-memory store for manual eligibility overrides."""

    def __init__(self) -> None:
        # Key: run_id -> list[ManualOverride]
        self._overrides: dict[str, list[ManualOverride]] = {}

    def save(self, override: ManualOverride) -> None:
        run_overrides = self._overrides.setdefault(override.run_id, [])
        # Replace if team override already exists for this run
        for idx, existing in enumerate(run_overrides):
            if existing.team_id == override.team_id:
                run_overrides[idx] = override.model_copy(deep=True)
                return
        run_overrides.append(override.model_copy(deep=True))

    def get_for_run(self, run_id: str) -> list[ManualOverride]:
        return [o.model_copy(deep=True) for o in self._overrides.get(run_id, [])]

    def get_for_team(self, run_id: str, team_id: str) -> Optional[ManualOverride]:
        for o in self._overrides.get(run_id, []):
            if o.team_id == team_id:
                return o.model_copy(deep=True)
        return None

    def reset(self) -> None:
        self._overrides.clear()


default_run_store = InMemoryRunStore()
default_override_store = InMemoryOverrideStore()
