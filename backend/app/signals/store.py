"""In-memory storage interfaces and implementations for signal extraction runs.

Enables historical reproducibility and audit logging of extracted signals per candidate
and team, behind a Protocol interface to facilitate seamless PostgreSQL integration.
"""

from __future__ import annotations

from typing import Optional, Protocol

from app.signals.schemas import ExtractionRunResponse


class ExtractionRunStoreProtocol(Protocol):
    """Protocol for signal extraction run persistence."""

    def save(self, record: ExtractionRunResponse, user_id: Optional[str] = None) -> None: ...
    def get(self, run_id: str) -> Optional[ExtractionRunResponse]: ...
    def list_runs(self, dataset_id: Optional[str] = None, user_id: Optional[str] = None) -> list[ExtractionRunResponse]: ...
    def list_summaries(
        self, limit: int = 50, dataset_id: Optional[str] = None, user_id: Optional[str] = None
    ) -> list[ExtractionRunSummary]: ...
    def get_dependent_counts(self, run_id: str) -> dict[str, int]: ...
    def delete(self, run_id: str, cascade: bool = False) -> bool: ...
    def reset(self) -> None: ...


class InMemoryExtractionRunStore:
    """Thread-safe in-memory store for signal extraction runs."""

    def __init__(self) -> None:
        self._runs: dict[str, ExtractionRunResponse] = {}

    def save(self, record: ExtractionRunResponse, user_id: Optional[str] = None) -> None:
        copy_rec = record.model_copy(deep=True)
        if user_id:
            copy_rec.user_id = user_id
        self._runs[record.run_id] = copy_rec

    def get(self, run_id: str) -> Optional[ExtractionRunResponse]:
        rec = self._runs.get(run_id)
        if rec is None:
            return None
        return rec.model_copy(deep=True)

    def list_runs(
        self, dataset_id: Optional[str] = None, user_id: Optional[str] = None
    ) -> list[ExtractionRunResponse]:
        runs = list(self._runs.values())
        if user_id:
            runs = [r for r in runs if getattr(r, "user_id", None) == user_id]
        if dataset_id:
            runs = [r for r in runs if r.dataset_id == dataset_id]
        runs.sort(key=lambda r: str(r.created_at or ""), reverse=True)
        return [r.model_copy(deep=True) for r in runs]

    def list_summaries(
        self, limit: int = 50, dataset_id: Optional[str] = None, user_id: Optional[str] = None
    ) -> list[ExtractionRunSummary]:
        from app.signals.schemas import ExtractionRunSummary

        runs = list(self._runs.values())
        if user_id:
            runs = [r for r in runs if getattr(r, "user_id", None) == user_id]
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
                user_id=getattr(r, "user_id", None),
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

    def get_dependent_counts(self, run_id: str) -> dict[str, int]:
        """Count downstream runs that reference this extraction run."""
        from app.storage import default_storage_factory
        ranking_store = default_storage_factory.get_ranking_run_store()
        scoring_store = default_storage_factory.get_scoring_run_store()
        elig_store = default_storage_factory.get_eligibility_run_store()

        ranking_count = sum(1 for r in ranking_store.list_runs() if getattr(r, "extraction_run_id", None) == run_id)
        scoring_count = sum(1 for r in scoring_store.list_runs() if getattr(r, "extraction_run_id", None) == run_id)
        elig_count = sum(1 for r in elig_store.list_runs() if getattr(r, "extraction_run_id", None) == run_id)

        return {
            "ranking_runs": ranking_count,
            "scoring_runs": scoring_count,
            "eligibility_runs": elig_count,
            "total": ranking_count + scoring_count + elig_count,
        }

    def delete(self, run_id: str, cascade: bool = False) -> bool:
        """Delete extraction run with optional cascade of dependent runs."""
        if run_id not in self._runs:
            return False

        counts = self.get_dependent_counts(run_id)
        if not cascade and counts["total"] > 0:
            raise ValueError(
                f"Cannot delete extraction run '{run_id}' because it has {counts['total']} dependent run(s). Use cascade=True to delete them."
            )

        if cascade:
            from app.storage import default_storage_factory
            ranking_store = default_storage_factory.get_ranking_run_store()
            scoring_store = default_storage_factory.get_scoring_run_store()
            elig_store = default_storage_factory.get_eligibility_run_store()

            for r in ranking_store.list_runs():
                if getattr(r, "extraction_run_id", None) == run_id:
                    ranking_store.delete(r.run_id)

            for r in scoring_store.list_runs():
                if getattr(r, "extraction_run_id", None) == run_id:
                    scoring_store.delete(r.run_id)

            for r in elig_store.list_runs():
                if getattr(r, "extraction_run_id", None) == run_id:
                    elig_store.delete(r.run_id)

        del self._runs[run_id]
        return True

    def reset(self) -> None:
        self._runs.clear()


from app.storage import DelegatingExtractionRunStore

default_extraction_run_store = DelegatingExtractionRunStore()
