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
    def delete(self, dataset_id: str) -> bool: ...
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
        records = list(self._datasets.values())
        records.sort(key=lambda d: str(d.uploaded_at), reverse=True)
        return [r.model_copy(deep=True) for r in records]

    def delete(self, dataset_id: str) -> bool:
        if dataset_id in self._datasets:
            del self._datasets[dataset_id]
            return True
        return False

    def reset(self) -> None:
        self._datasets.clear()


from app.storage import DelegatingDatasetStore

default_dataset_store = DelegatingDatasetStore()
