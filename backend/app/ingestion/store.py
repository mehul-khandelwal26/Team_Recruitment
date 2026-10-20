"""In-memory storage interfaces and implementations for uploaded datasets.

Provides thread-safe in-memory dataset persistence for development and testing,
behind a Protocol to enable clean PostgreSQL integration.
"""

from __future__ import annotations

from typing import Optional, Protocol

from app.schemas.ingestion import DatasetRecord


class DatasetStoreProtocol(Protocol):
    """Protocol defining persistence interface for uploaded dataset records."""

    def save(self, record: DatasetRecord) -> DatasetRecord: ...
    def get(self, dataset_id: str) -> Optional[DatasetRecord]: ...
    def list_datasets(self) -> list[DatasetRecord]: ...
    def list_summaries(self, limit: int = 50) -> list[DatasetSummary]: ...
    def get_dependent_counts(self, dataset_id: str) -> dict[str, int]: ...
    def delete(self, dataset_id: str, cascade: bool = False) -> bool: ...
    def reset(self) -> None: ...


class InMemoryDatasetStore:
    """Thread-safe in-memory store for dataset records."""

    def __init__(self) -> None:
        self._datasets: dict[str, DatasetRecord] = {}

    def save(self, record: DatasetRecord) -> DatasetRecord:
        self._datasets[record.dataset_id] = record.model_copy(deep=True)
        return record

    def get(self, dataset_id: str) -> Optional[DatasetRecord]:
        rec = self._datasets.get(dataset_id)
        if rec is None:
            return None
        return rec.model_copy(deep=True)

    def list_datasets(self) -> list[DatasetRecord]:
        indexed_records = list(enumerate(self._datasets.values()))
        indexed_records.sort(
            key=lambda item: (
                str(item[1].uploaded_at or ""),
                item[0],
            ),
            reverse=True,
        )
        return [r.model_copy(deep=True) for _, r in indexed_records]

    def list_summaries(self, limit: int = 50) -> list[DatasetSummary]:
        from app.schemas.ingestion import DatasetSummary

        indexed_records = list(enumerate(self._datasets.values()))
        indexed_records.sort(
            key=lambda item: (
                str(item[1].uploaded_at or ""),
                item[0],
            ),
            reverse=True,
        )
        records = [r for _, r in indexed_records]
        items = records[:limit]
        return [
            DatasetSummary(
                dataset_id=r.dataset_id,
                filename=r.filename,
                file_type=r.file_type,
                teams_count=r.teams_count,
                members_count=r.members_count,
                uploaded_at=str(r.uploaded_at),
                warnings_count=len(r.warnings or []),
            )
            for r in items
        ]


    def get_dependent_counts(self, dataset_id: str) -> dict[str, int]:
        """Count downstream runs that reference this dataset directly or via its extractions."""
        from app.storage import default_storage_factory
        ranking_store = default_storage_factory.get_ranking_run_store()
        scoring_store = default_storage_factory.get_scoring_run_store()
        elig_store = default_storage_factory.get_eligibility_run_store()
        ext_store = default_storage_factory.get_extraction_run_store()

        ext_runs = ext_store.list_runs(dataset_id=dataset_id)
        ext_ids = {r.run_id for r in ext_runs}

        ranking_count = sum(
            1 for r in ranking_store.list_runs()
            if getattr(r, "dataset_id", None) == dataset_id or getattr(r, "extraction_run_id", None) in ext_ids
        )
        scoring_count = sum(
            1 for r in scoring_store.list_runs()
            if getattr(r, "dataset_id", None) == dataset_id or getattr(r, "extraction_run_id", None) in ext_ids
        )
        elig_count = sum(
            1 for r in elig_store.list_runs()
            if getattr(r, "dataset_id", None) == dataset_id or getattr(r, "extraction_run_id", None) in ext_ids
        )
        ext_count = len(ext_ids)

        return {
            "ranking_runs": ranking_count,
            "scoring_runs": scoring_count,
            "eligibility_runs": elig_count,
            "extraction_runs": ext_count,
            "total": ranking_count + scoring_count + elig_count + ext_count,
        }

    def delete(self, dataset_id: str, cascade: bool = False) -> bool:
        """Delete dataset with optional cascade of dependent runs."""
        if dataset_id not in self._datasets:
            return False

        counts = self.get_dependent_counts(dataset_id)
        if not cascade and counts["total"] > 0:
            raise ValueError(
                f"Cannot delete dataset '{dataset_id}' because it has {counts['total']} dependent run(s). Use cascade=True to delete them."
            )

        if cascade:
            from app.storage import default_storage_factory
            ranking_store = default_storage_factory.get_ranking_run_store()
            scoring_store = default_storage_factory.get_scoring_run_store()
            elig_store = default_storage_factory.get_eligibility_run_store()
            ext_store = default_storage_factory.get_extraction_run_store()

            ext_runs = ext_store.list_runs(dataset_id=dataset_id)
            ext_ids = {r.run_id for r in ext_runs}

            for r in ranking_store.list_runs():
                if getattr(r, "dataset_id", None) == dataset_id or getattr(r, "extraction_run_id", None) in ext_ids:
                    ranking_store.delete(r.run_id)

            for r in scoring_store.list_runs():
                if getattr(r, "dataset_id", None) == dataset_id or getattr(r, "extraction_run_id", None) in ext_ids:
                    scoring_store.delete(r.run_id)

            for r in elig_store.list_runs():
                if getattr(r, "dataset_id", None) == dataset_id or getattr(r, "extraction_run_id", None) in ext_ids:
                    elig_store.delete(r.run_id)

            for ext_id in ext_ids:
                ext_store.delete(ext_id, cascade=True)

        del self._datasets[dataset_id]
        return True

    def reset(self) -> None:
        self._datasets.clear()


from app.storage import DelegatingDatasetStore

default_dataset_store = DelegatingDatasetStore()
