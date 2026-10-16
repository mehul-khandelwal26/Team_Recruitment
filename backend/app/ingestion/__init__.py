"""Data ingestion – CSV/JSON file parsing and normalisation."""

from app.ingestion.discovery import discover_fields_from_bytes
from app.ingestion.parser import parse_csv, parse_json
from app.ingestion.store import (
    DatasetStoreProtocol,
    InMemoryDatasetStore,
    default_dataset_store,
)

__all__ = [
    "discover_fields_from_bytes",
    "parse_csv",
    "parse_json",
    "DatasetStoreProtocol",
    "InMemoryDatasetStore",
    "default_dataset_store",
]
