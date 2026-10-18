"""Centralized storage factory and delegating store proxies.

Guarantees:
- Centralized storage selection based on STORAGE_BACKEND ('memory' or 'postgres').
- Memory mode remains default unless configured otherwise.
- Explicit engine injection for test isolation: injected engines are strictly used
  by PostgreSQL stores, avoiding fallback to default or global engines.
- Lazy connection management: importing storage or store modules does not connect to DB.
- Existing public store interfaces and default_* variables remain fully compatible.
- Selecting PostgreSQL mode never silently falls back to memory mode.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Optional

import sqlalchemy as sa
from sqlalchemy.engine import Engine

from app.config import STORAGE_BACKEND, assert_safe_test_database
from app.db.stores import (
    PostgresDatasetStore,
    PostgresEligibilityRunStore,
    PostgresExtractionRunStore,
    PostgresManualOverrideStore,
    PostgresRankingRunStore,
    PostgresRuleConfigStore,
    PostgresScoringConfigStore,
    PostgresScoringRunStore,
)

if TYPE_CHECKING:
    from app.ranking.schemas import RankingRunResponse, RankingRunSummaryItem
    from app.ranking.store import InMemoryRankingRunStore, RankingRunStoreProtocol
    from app.rules.config_store import RuleConfigStore
    from app.schemas.ingestion import DatasetRecord, DatasetSummary
    from app.signals.schemas import ExtractionRunResponse, ExtractionRunSummary
    from app.rules.schemas import (
        EligibilityRunResponse,
        ManualOverride,
        RuleConfiguration,
        RuleConfigurationUpdate,
    )
    from app.rules.store import (
        InMemoryOverrideStore,
        InMemoryRunStore,
        OverrideStore,
        RunStore,
    )
    from app.scoring.config_store import ScoringConfigStore
    from app.scoring.schemas import (
        ScoringConfiguration,
        ScoringConfigurationUpdate,
        ScoringRunResponse,
    )
    from app.scoring.store import InMemoryScoringRunStore, ScoringRunStoreProtocol


class StorageFactory:
    """Centralized factory managing recruitment data store instances."""

    def __init__(
        self,
        backend: Optional[str] = None,
        engine: Optional[Engine] = None,
    ) -> None:
        self._backend: Optional[str] = backend
        self._engine: Optional[Engine] = engine
        self._stores: dict[str, Any] = {}

    @property
    def backend(self) -> str:
        """Return the effective storage backend ('memory' or 'postgres')."""
        if self._backend is not None:
            return self._backend.strip().lower()
        return os.getenv("STORAGE_BACKEND", STORAGE_BACKEND).strip().lower()

    @property
    def engine(self) -> Optional[Engine]:
        """Return currently injected engine, if any."""
        return self._engine

    def configure(
        self,
        backend: Optional[str] = None,
        engine: Optional[Engine] = None,
    ) -> None:
        """Reconfigure storage factory backend and/or injected engine."""
        self._backend = backend
        self._engine = engine
        self._stores.clear()

    def reset_stores(self) -> None:
        """Call reset() on all instantiated stores that support it."""
        for store in self._stores.values():
            if hasattr(store, "reset"):
                store.reset()

    # --- Store Accessors ---

    def get_rule_config_store(self) -> Any:
        key = f"rule_config_{self.backend}"
        if key not in self._stores:
            if self.backend == "postgres":
                self._stores[key] = PostgresRuleConfigStore(engine=self._engine)
            else:
                from app.rules.config_store import RuleConfigStore
                self._stores[key] = RuleConfigStore()
        return self._stores[key]

    def get_scoring_config_store(self) -> Any:
        key = f"scoring_config_{self.backend}"
        if key not in self._stores:
            if self.backend == "postgres":
                self._stores[key] = PostgresScoringConfigStore(engine=self._engine)
            else:
                from app.scoring.config_store import ScoringConfigStore
                self._stores[key] = ScoringConfigStore()
        return self._stores[key]

    def get_eligibility_run_store(self) -> Any:
        key = f"eligibility_run_{self.backend}"
        if key not in self._stores:
            if self.backend == "postgres":
                self._stores[key] = PostgresEligibilityRunStore(engine=self._engine)
            else:
                from app.rules.store import InMemoryRunStore
                self._stores[key] = InMemoryRunStore()
        return self._stores[key]

    def get_manual_override_store(self) -> Any:
        key = f"manual_override_{self.backend}"
        if key not in self._stores:
            if self.backend == "postgres":
                self._stores[key] = PostgresManualOverrideStore(engine=self._engine)
            else:
                from app.rules.store import InMemoryOverrideStore
                self._stores[key] = InMemoryOverrideStore()
        return self._stores[key]

    def get_scoring_run_store(self) -> Any:
        key = f"scoring_run_{self.backend}"
        if key not in self._stores:
            if self.backend == "postgres":
                self._stores[key] = PostgresScoringRunStore(engine=self._engine)
            else:
                from app.scoring.store import InMemoryScoringRunStore
                self._stores[key] = InMemoryScoringRunStore()
        return self._stores[key]

    def get_ranking_run_store(self) -> Any:
        key = f"ranking_run_{self.backend}"
        if key not in self._stores:
            if self.backend == "postgres":
                self._stores[key] = PostgresRankingRunStore(engine=self._engine)
            else:
                from app.ranking.store import InMemoryRankingRunStore
                self._stores[key] = InMemoryRankingRunStore()
        return self._stores[key]

    def get_dataset_store(self) -> Any:
        key = f"dataset_{self.backend}"
        if key not in self._stores:
            if self.backend == "postgres":
                self._stores[key] = PostgresDatasetStore(engine=self._engine)
            else:
                from app.ingestion.store import InMemoryDatasetStore
                self._stores[key] = InMemoryDatasetStore()
        return self._stores[key]

    def get_extraction_run_store(self) -> Any:
        key = f"extraction_run_{self.backend}"
        if key not in self._stores:
            if self.backend == "postgres":
                self._stores[key] = PostgresExtractionRunStore(engine=self._engine)
            else:
                from app.signals.store import InMemoryExtractionRunStore
                self._stores[key] = InMemoryExtractionRunStore()
        return self._stores[key]


# Global singleton factory instance
default_storage_factory = StorageFactory()


# ---------------------------------------------------------------------------
# Delegating Store Proxies
# ---------------------------------------------------------------------------


class DelegatingRuleConfigStore:
    """Delegates rule config operations to the factory-selected active store."""

    def __init__(self, factory: Optional[StorageFactory] = None) -> None:
        self._factory = factory

    @property
    def _store(self) -> Any:
        f = self._factory or default_storage_factory
        return f.get_rule_config_store()

    def get(self, config_id: str, version: Optional[int] = None) -> Optional[RuleConfiguration]:
        return self._store.get(config_id, version=version)

    def list_latest(self) -> list[RuleConfiguration]:
        return self._store.list_latest()

    def list_versions(self, config_id: str) -> list[int]:
        return self._store.list_versions(config_id)

    def save(self, config: RuleConfiguration) -> RuleConfiguration:
        return self._store.save(config)

    def update(
        self, config_id: str, update_payload: RuleConfigurationUpdate
    ) -> Optional[RuleConfiguration]:
        return self._store.update(config_id, update_payload)

    def delete(self, config_id: str) -> bool:
        return self._store.delete(config_id)

    def reset(self) -> None:
        return self._store.reset()

    def load_presets(self) -> None:
        if hasattr(self._store, "load_presets"):
            return self._store.load_presets()


class DelegatingScoringConfigStore:
    """Delegates scoring config operations to the factory-selected active store."""

    def __init__(self, factory: Optional[StorageFactory] = None) -> None:
        self._factory = factory

    @property
    def _store(self) -> Any:
        f = self._factory or default_storage_factory
        return f.get_scoring_config_store()

    def get(self, config_id: str, version: Optional[int] = None) -> Optional[ScoringConfiguration]:
        return self._store.get(config_id, version=version)

    def list_latest(self) -> list[ScoringConfiguration]:
        return self._store.list_latest()

    def list_versions(self, config_id: str) -> list[int]:
        return self._store.list_versions(config_id)

    def save(self, config: ScoringConfiguration) -> ScoringConfiguration:
        return self._store.save(config)

    def update(
        self, config_id: str, update_payload: ScoringConfigurationUpdate
    ) -> Optional[ScoringConfiguration]:
        return self._store.update(config_id, update_payload)

    def delete(self, config_id: str) -> bool:
        if hasattr(self._store, "delete"):
            return self._store.delete(config_id)
        return False

    def reset(self) -> None:
        return self._store.reset()

    def load_presets(self) -> None:
        if hasattr(self._store, "load_presets"):
            return self._store.load_presets()


class DelegatingRunStore:
    """Delegates eligibility run operations to the factory-selected active store."""

    def __init__(self, factory: Optional[StorageFactory] = None) -> None:
        self._factory = factory

    @property
    def _store(self) -> Any:
        f = self._factory or default_storage_factory
        return f.get_eligibility_run_store()

    def save(self, record: EligibilityRunResponse) -> None:
        self._store.save(record)

    def get(self, run_id: str) -> Optional[EligibilityRunResponse]:
        return self._store.get(run_id)

    def list_runs(self, config_id: Optional[str] = None) -> list[EligibilityRunResponse]:
        return self._store.list_runs(config_id=config_id)

    def reset(self) -> None:
        return self._store.reset()


class DelegatingOverrideStore:
    """Delegates manual override operations to the factory-selected active store."""

    def __init__(self, factory: Optional[StorageFactory] = None) -> None:
        self._factory = factory

    @property
    def _store(self) -> Any:
        f = self._factory or default_storage_factory
        return f.get_manual_override_store()

    def save(self, override: ManualOverride) -> None:
        self._store.save(override)

    def get_for_run(self, run_id: str) -> list[ManualOverride]:
        return self._store.get_for_run(run_id)

    def get_for_team(self, run_id: str, team_id: str) -> Optional[ManualOverride]:
        return self._store.get_for_team(run_id, team_id)

    def reset(self) -> None:
        return self._store.reset()


class DelegatingScoringRunStore:
    """Delegates scoring run operations to the factory-selected active store."""

    def __init__(self, factory: Optional[StorageFactory] = None) -> None:
        self._factory = factory

    @property
    def _store(self) -> Any:
        f = self._factory or default_storage_factory
        return f.get_scoring_run_store()

    def save(self, record: ScoringRunResponse) -> None:
        self._store.save(record)

    def get(self, run_id: str) -> Optional[ScoringRunResponse]:
        return self._store.get(run_id)

    def list_runs(self, config_id: Optional[str] = None) -> list[ScoringRunResponse]:
        return self._store.list_runs(config_id=config_id)

    def reset(self) -> None:
        return self._store.reset()


class DelegatingRankingRunStore:
    """Delegates ranking run operations to the factory-selected active store."""

    def __init__(self, factory: Optional[StorageFactory] = None) -> None:
        self._factory = factory

    @property
    def _store(self) -> Any:
        f = self._factory or default_storage_factory
        return f.get_ranking_run_store()

    def save(self, record: RankingRunResponse) -> None:
        self._store.save(record)

    def get(self, run_id: str) -> Optional[RankingRunResponse]:
        return self._store.get(run_id)

    def list_runs(self) -> list[RankingRunResponse]:
        return self._store.list_runs()

    def list_summaries(self, limit: int = 50) -> list[RankingRunSummaryItem]:
        return self._store.list_summaries(limit=limit)

    def reset(self) -> None:
        return self._store.reset()


class DelegatingDatasetStore:
    """Delegates dataset persistence operations to the factory-selected active store."""

    def __init__(self, factory: Optional[StorageFactory] = None) -> None:
        self._factory = factory

    @property
    def _store(self) -> Any:
        f = self._factory or default_storage_factory
        return f.get_dataset_store()

    def save(self, record: DatasetRecord) -> DatasetRecord:
        return self._store.save(record)

    def get(self, dataset_id: str) -> Optional[DatasetRecord]:
        return self._store.get(dataset_id)

    def list_datasets(self) -> list[DatasetRecord]:
        return self._store.list_datasets()

    def list_summaries(self, limit: int = 50) -> list[DatasetSummary]:
        return self._store.list_summaries(limit=limit)

    def delete(self, dataset_id: str) -> bool:
        return self._store.delete(dataset_id)

    def reset(self) -> None:
        return self._store.reset()


class DelegatingExtractionRunStore:
    """Delegates extraction run operations to the factory-selected active store."""

    def __init__(self, factory: Optional[StorageFactory] = None) -> None:
        self._factory = factory

    @property
    def _store(self) -> Any:
        f = self._factory or default_storage_factory
        return f.get_extraction_run_store()

    def save(self, record: ExtractionRunResponse) -> None:
        self._store.save(record)

    def get(self, run_id: str) -> Optional[ExtractionRunResponse]:
        return self._store.get(run_id)

    def list_runs(self, dataset_id: Optional[str] = None) -> list[ExtractionRunResponse]:
        return self._store.list_runs(dataset_id=dataset_id)

    def list_summaries(
        self, limit: int = 50, dataset_id: Optional[str] = None
    ) -> list[ExtractionRunSummary]:
        return self._store.list_summaries(limit=limit, dataset_id=dataset_id)

    def reset(self) -> None:
        return self._store.reset()



# ---------------------------------------------------------------------------
# Test Reset Helper (Section 14E)
# ---------------------------------------------------------------------------


def reset_test_database(engine: Engine) -> None:
    """Safely truncate test tables on the validated test database only.

    Strictly verifies that engine URL matches TEST_DATABASE_URL and passes
    assert_safe_test_database before executing. Never called automatically by app.
    Limited strictly to the 8 existing project tables.
    """
    url_str = engine.url.render_as_string(hide_password=False)
    assert_safe_test_database(url_str)

    tables = [
        "ranking_runs",
        "scoring_runs",
        "manual_overrides",
        "eligibility_runs",
        "extraction_runs",
        "datasets",
        "scoring_configurations",
        "rule_configurations",
    ]
    with engine.begin() as conn:
        conn.execute(sa.text(f"TRUNCATE TABLE {', '.join(tables)} CASCADE;"))
