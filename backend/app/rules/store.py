"""In-memory storage interfaces and implementations for evaluation runs and manual overrides.

Enables clean separation between:
1. Historical evaluation runs (immutable snapshot of calculated decisions).
2. Organizer manual overrides (independent audit log; original runs are never mutated).

Both stores are placed behind small protocols to facilitate future database persistence.
"""

from __future__ import annotations

from typing import Optional, Protocol

from app.rules.schemas import EligibilityRunResponse, EligibilityStatus, ManualOverride


# ---------------------------------------------------------------------------
# Protocols (Interfaces)
# ---------------------------------------------------------------------------


class RunStore(Protocol):
    """Protocol for eligibility run record persistence."""

    def save(self, record: EligibilityRunResponse) -> None: ...
    def get(self, run_id: str) -> Optional[EligibilityRunResponse]: ...
    def list_runs(self, config_id: Optional[str] = None) -> list[EligibilityRunResponse]: ...
    def delete(self, run_id: str) -> bool: ...
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

    def delete(self, run_id: str) -> bool:
        """Delete eligibility run by run_id."""
        if run_id in self._runs:
            del self._runs[run_id]
            return True
        return False

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


from app.storage import DelegatingOverrideStore, DelegatingRunStore

default_run_store = DelegatingRunStore()
default_override_store = DelegatingOverrideStore()


def get_effective_run(
    run_id: str,
    run_store: Optional[RunStore] = None,
    override_store: Optional[OverrideStore] = None,
) -> Optional[EligibilityRunResponse]:
    """Retrieve an evaluation run's results with any manual overrides merged in.

    Applies manual overrides to team status, reasons, has_override, and recalculates
    the summary counts. Returns None if the run does not exist.
    """
    r_store = run_store or default_run_store
    o_store = override_store or default_override_store

    run_record = r_store.get(run_id)
    if run_record is None:
        return None

    overrides = o_store.get_for_run(run_id)
    override_by_team = {o.team_id: o for o in overrides}

    eligible_count = 0
    ineligible_count = 0
    needs_review_count = 0

    for team in run_record.teams:
        if team.team_id in override_by_team:
            o = override_by_team[team.team_id]
            team.has_override = True
            team.override = o
            team.status = o.override_status
            team.reasons = [
                f"Manual override by {o.overridden_by} to {o.override_status.value}: {o.reason}"
            ] + team.reasons

        if team.status == EligibilityStatus.ELIGIBLE:
            eligible_count += 1
        elif team.status == EligibilityStatus.INELIGIBLE:
            ineligible_count += 1
        elif team.status == EligibilityStatus.NEEDS_REVIEW:
            needs_review_count += 1

    run_record.summary.eligible_count = eligible_count
    run_record.summary.ineligible_count = ineligible_count
    run_record.summary.needs_review_count = needs_review_count

    return run_record

