"""In-memory storage interfaces and implementations for signal extraction runs.

Enables historical reproducibility and audit logging of extracted signals per candidate
and team, behind a Protocol interface to facilitate seamless PostgreSQL integration.
"""

from __future__ import annotations

from typing import Optional, Protocol

from app.signals.schemas import ExtractionRunResponse


class ExtractionRunStoreProtocol(Protocol):
    """Protocol for signal extraction run persistence."""

    def save(self, record: ExtractionRunResponse) -> None: ...
    def get(self, run_id: str) -> Optional[ExtractionRunResponse]: ...
    def list_runs(self, dataset_id: Optional[str] = None) -> list[ExtractionRunResponse]: ...
    def list_summaries(
        self, limit: int = 50, dataset_id: Optional[str] = None
    ) -> list[ExtractionRunSummary]: ...
    def reset(self) -> None: ...


class InMemoryExtractionRunStore:
    """Thread-safe in-memory store for signal extraction runs."""

    def __init__(self) -> None:
        self._runs: dict[str, ExtractionRunResponse] = {}

    def save(self, record: ExtractionRunResponse) -> None:
        self._runs[record.run_id] = record.model_copy(deep=True)

    def get(self, run_id: str) -> Optional[ExtractionRunResponse]:
        rec = self._runs.get(run_id)
        if rec is None:
            return None
        return rec.model_copy(deep=True)

    def list_runs(self, dataset_id: Optional[str] = None) -> list[ExtractionRunResponse]:
        runs = list(self._runs.values())
        if dataset_id:
            runs = [r for r in runs if r.dataset_id == dataset_id]
        runs.sort(key=lambda r: str(r.created_at or ""), reverse=True)
        return [r.model_copy(deep=True) for r in runs]

    def list_summaries(
        self, limit: int = 50, dataset_id: Optional[str] = None
    ) -> list[ExtractionRunSummary]:
        from app.signals.schemas import ExtractionRunSummary

        runs = list(self._runs.values())
        if dataset_id:
            runs = [r for r in runs if r.dataset_id == dataset_id]
        runs.sort(
            key=lambda r: (
                str(r.created_at or ""),
                str(r.run_id or ""),
            ),
            reverse=True,
        )
        items = runs[:limit]
        return [
            ExtractionRunSummary(
                run_id=r.run_id,
                dataset_id=r.dataset_id,
                created_at=str(r.created_at or ""),
                selected_signals=list(r.selected_signals or []),
                total_teams=r.total_teams,
                total_members=r.total_members,
                warnings_count=len(r.warnings or []),
                errors_count=len(r.errors or []),
            )
            for r in items
        ]


    def reset(self) -> None:
        self._runs.clear()


from app.storage import DelegatingExtractionRunStore

default_extraction_run_store = DelegatingExtractionRunStore()
