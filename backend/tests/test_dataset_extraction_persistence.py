"""Comprehensive integration tests for Dataset and Extraction Run PostgreSQL persistence.

Covers:
1. Module-scoped Alembic head migration fixture against TEST_DATABASE_URL (no downgrade afterwards).
2. PostgresDatasetStore: CRUD, uploaded_at sorting, missing record handling, ON CONFLICT DO UPDATE upsert, deletion.
3. PostgresExtractionRunStore: CRUD, dataset_id filtering, created_at sorting, nullable dataset_id, ON CONFLICT DO UPDATE upsert.
4. Database Constraints: Foreign Key (extraction_runs.dataset_id -> datasets.dataset_id) RESTRICT on delete, FK violation on non-existent dataset.
5. Storage Factory: storage selection for memory vs postgres, engine injection, no silent fallback.
6. API Workflows (with PostgreSQL backend):
   - Ingestion upload persists dataset and returns dataset_id.
   - Ingestion invalid upload does not persist dataset.
   - Signal extraction from file persists both dataset and extraction run linked together.
   - Signal extraction by dataset_id reference loads teams from dataset and persists run.
   - Signal extraction with missing dataset_id returns 404.
   - GET /api/ingestion/datasets/{dataset_id} and GET /api/ingestion/datasets.
   - GET /api/signals/runs/{run_id} and GET /api/signals/runs.
   - Downstream endpoints (rules, scoring, ranking) propagate and persist dataset_id and extraction_run_id.
"""

from __future__ import annotations

import datetime
import io
import json
import os
from typing import Any
import pytest
from fastapi.testclient import TestClient
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, OperationalError

from app.config import assert_safe_test_database
from app.db.models import DatasetModel, ExtractionRunModel
from app.db.seeding import seed_database_presets
from app.db.session import create_app_engine
from app.db.stores import PostgresDatasetStore, PostgresExtractionRunStore
from app.main import app
from app.schemas.ingestion import DatasetRecord, TeamSchema, MemberSchema
from app.signals.schemas import (
    ExtractedSignal,
    ExtractionRunResponse,
    MemberExtractionResult,
    SignalStatus,
    TeamExtractionResult,
)
from app.storage import (
    StorageFactory,
    default_storage_factory,
    reset_test_database,
)

# Skip entire module if TEST_DATABASE_URL is not set
TEST_DB_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DB_URL,
    reason="TEST_DATABASE_URL is not configured; skipping PostgreSQL integration tests as required.",
)


@pytest.fixture(scope="module")
def migrated_test_db():
    """Module-scoped fixture: validates TEST_DATABASE_URL and runs alembic upgrade head once."""
    assert_safe_test_database(TEST_DB_URL)

    from alembic import command
    from alembic.config import Config

    ini_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    alembic_cfg = Config(ini_path)
    alembic_cfg.attributes["override_url"] = TEST_DB_URL

    command.upgrade(alembic_cfg, "head")
    engine = create_app_engine(url=TEST_DB_URL)

    yield engine

    engine.dispose()


@pytest.fixture(autouse=True)
def clean_test_db(migrated_test_db):
    """Truncate the 8 project tables and configure postgres backend before each test."""
    reset_test_database(migrated_test_db)
    default_storage_factory.configure(backend="postgres", engine=migrated_test_db)
    yield
    reset_test_database(migrated_test_db)
    default_storage_factory.configure(backend="memory", engine=None)


# ===========================================================================
# 1. Dataset Store Tests
# ===========================================================================


class TestPostgresDatasetStore:
    def test_create_and_retrieve_dataset(self, migrated_test_db):
        store = PostgresDatasetStore(engine=migrated_test_db)
        record = DatasetRecord(
            dataset_id="ds_alpha_01",
            filename="hackathon_registrations.csv",
            file_type="csv",
            teams_count=2,
            members_count=4,
            uploaded_at="2026-10-16T12:00:00+00:00",
            mapping={"team_name": "TeamName"},
            warnings=["Column X was ignored"],
            unmapped_fields=["custom_col"],
            created_at="2026-10-16T12:00:00+00:00",
            payload={"teams": [{"team_id": "T1", "team_name": "Alpha"}]},
        )
        saved = store.save(record)
        assert saved.dataset_id == "ds_alpha_01"
        assert saved.filename == "hackathon_registrations.csv"
        assert saved.file_type == "csv"
        assert saved.teams_count == 2
        assert saved.members_count == 4
        assert saved.mapping == {"team_name": "TeamName"}
        assert saved.warnings == ["Column X was ignored"]
        assert saved.unmapped_fields == ["custom_col"]
        assert saved.payload == {"teams": [{"team_id": "T1", "team_name": "Alpha"}]}

        retrieved = store.get("ds_alpha_01")
        assert retrieved is not None
        assert retrieved.dataset_id == "ds_alpha_01"
        assert retrieved.filename == "hackathon_registrations.csv"
        assert retrieved.teams_count == 2
        assert retrieved.payload["teams"][0]["team_id"] == "T1"

    def test_retrieve_missing_dataset_returns_none(self, migrated_test_db):
        store = PostgresDatasetStore(engine=migrated_test_db)
        assert store.get("nonexistent_ds") is None

    def test_list_datasets_ordering(self, migrated_test_db):
        store = PostgresDatasetStore(engine=migrated_test_db)
        t1 = "2026-10-15T10:00:00+00:00"
        t2 = "2026-10-16T10:00:00+00:00"
        t3 = "2026-10-17T10:00:00+00:00"

        store.save(DatasetRecord(dataset_id="ds_1", filename="d1.csv", file_type="csv", uploaded_at=t1))
        store.save(DatasetRecord(dataset_id="ds_3", filename="d3.csv", file_type="csv", uploaded_at=t3))
        store.save(DatasetRecord(dataset_id="ds_2", filename="d2.csv", file_type="csv", uploaded_at=t2))

        datasets = store.list_datasets()
        assert len(datasets) == 3
        # Should be ordered uploaded_at.desc()
        assert [d.dataset_id for d in datasets] == ["ds_3", "ds_2", "ds_1"]

    def test_on_conflict_upsert_dataset(self, migrated_test_db):
        store = PostgresDatasetStore(engine=migrated_test_db)
        r1 = DatasetRecord(
            dataset_id="ds_upsert",
            filename="orig.csv",
            file_type="csv",
            teams_count=1,
            members_count=2,
            payload={"teams": []},
        )
        store.save(r1)

        r2 = DatasetRecord(
            dataset_id="ds_upsert",
            filename="updated.csv",
            file_type="csv",
            teams_count=5,
            members_count=15,
            payload={"teams": [{"team_id": "T1"}]},
        )
        store.save(r2)

        retrieved = store.get("ds_upsert")
        assert retrieved is not None
        assert retrieved.filename == "updated.csv"
        assert retrieved.teams_count == 5
        assert retrieved.members_count == 15
        assert len(retrieved.payload["teams"]) == 1

    def test_delete_dataset(self, migrated_test_db):
        store = PostgresDatasetStore(engine=migrated_test_db)
        store.save(DatasetRecord(dataset_id="ds_del", filename="del.csv", file_type="csv"))
        assert store.get("ds_del") is not None

        deleted = store.delete("ds_del")
        assert deleted is True
        assert store.get("ds_del") is None

        # Deleting nonexistent dataset returns False
        assert store.delete("ds_del") is False


# ===========================================================================
# 2. Extraction Run Store Tests
# ===========================================================================


class TestPostgresExtractionRunStore:
    def test_create_and_retrieve_extraction_run(self, migrated_test_db):
        ds_store = PostgresDatasetStore(engine=migrated_test_db)
        run_store = PostgresExtractionRunStore(engine=migrated_test_db)

        # Save dataset first for FK
        ds_store.save(DatasetRecord(dataset_id="ds_ext_01", filename="ds1.csv", file_type="csv"))

        rec = ExtractionRunResponse(
            run_id="run_ext_001",
            dataset_id="ds_ext_01",
            analyzers_executed=["academic", "github"],
            total_teams=1,
            total_members=1,
            teams=[
                TeamExtractionResult(
                    team_id="T1",
                    team_name="Team 1",
                    member_results=[
                        MemberExtractionResult(
                            member_id="M1",
                            name="Alice",
                            signals=[
                                ExtractedSignal(
                                    signal_key="academic_cgpa",
                                    category="academic",
                                    status=SignalStatus.EXTRACTED,
                                    value=9.5,
                                )
                            ],
                        )
                    ],
                )
            ],
            created_at="2026-10-16T14:00:00+00:00",
        )

        run_store.save(rec)

        retrieved = run_store.get("run_ext_001")
        assert retrieved is not None
        assert retrieved.run_id == "run_ext_001"
        assert retrieved.dataset_id == "ds_ext_01"
        assert retrieved.analyzers_executed == ["academic", "github"]
        assert retrieved.total_teams == 1
        assert retrieved.total_members == 1
        assert len(retrieved.teams) == 1
        assert retrieved.teams[0].member_results[0].signals[0].value == 9.5

    def test_retrieve_missing_run_returns_none(self, migrated_test_db):
        run_store = PostgresExtractionRunStore(engine=migrated_test_db)
        assert run_store.get("nonexistent_run") is None

    def test_list_extraction_runs_filtering_and_ordering(self, migrated_test_db):
        ds_store = PostgresDatasetStore(engine=migrated_test_db)
        run_store = PostgresExtractionRunStore(engine=migrated_test_db)

        ds_store.save(DatasetRecord(dataset_id="ds_A", filename="a.csv", file_type="csv"))
        ds_store.save(DatasetRecord(dataset_id="ds_B", filename="b.csv", file_type="csv"))

        t1 = "2026-10-15T10:00:00+00:00"
        t2 = "2026-10-16T10:00:00+00:00"
        t3 = "2026-10-17T10:00:00+00:00"

        run_store.save(ExtractionRunResponse(run_id="run_1", dataset_id="ds_A", total_teams=1, total_members=1, created_at=t1))
        run_store.save(ExtractionRunResponse(run_id="run_2", dataset_id="ds_B", total_teams=1, total_members=1, created_at=t2))
        run_store.save(ExtractionRunResponse(run_id="run_3", dataset_id="ds_A", total_teams=1, total_members=1, created_at=t3))

        # List all: ordered created_at DESC
        all_runs = run_store.list_runs()
        assert len(all_runs) == 3
        assert [r.run_id for r in all_runs] == ["run_3", "run_2", "run_1"]

        # List filtered by dataset_id="ds_A"
        ds_a_runs = run_store.list_runs(dataset_id="ds_A")
        assert len(ds_a_runs) == 2
        assert [r.run_id for r in ds_a_runs] == ["run_3", "run_1"]

        # List filtered by dataset_id="ds_B"
        ds_b_runs = run_store.list_runs(dataset_id="ds_B")
        assert len(ds_b_runs) == 1
        assert ds_b_runs[0].run_id == "run_2"

    def test_nullable_dataset_id_allowed(self, migrated_test_db):
        run_store = PostgresExtractionRunStore(engine=migrated_test_db)
        rec = ExtractionRunResponse(
            run_id="run_no_ds",
            dataset_id=None,
            total_teams=0,
            total_members=0,
            teams=[],
        )
        run_store.save(rec)

        retrieved = run_store.get("run_no_ds")
        assert retrieved is not None
        assert retrieved.run_id == "run_no_ds"
        assert retrieved.dataset_id is None

    def test_on_conflict_upsert_extraction_run(self, migrated_test_db):
        run_store = PostgresExtractionRunStore(engine=migrated_test_db)
        r1 = ExtractionRunResponse(
            run_id="run_upsert",
            dataset_id=None,
            analyzers_executed=["academic"],
            total_teams=1,
            total_members=1,
            teams=[],
        )
        run_store.save(r1)

        r2 = ExtractionRunResponse(
            run_id="run_upsert",
            dataset_id=None,
            analyzers_executed=["academic", "github"],
            total_teams=5,
            total_members=10,
            teams=[],
        )
        run_store.save(r2)

        retrieved = run_store.get("run_upsert")
        assert retrieved is not None
        assert retrieved.analyzers_executed == ["academic", "github"]
        assert retrieved.total_teams == 5
        assert retrieved.total_members == 10


# ===========================================================================
# 3. Constraint and Foreign Key Enforcement
# ===========================================================================


class TestDatasetExtractionConstraints:
    def test_extraction_run_foreign_key_violation(self, migrated_test_db):
        run_store = PostgresExtractionRunStore(engine=migrated_test_db)
        # dataset_id "nonexistent_ds" does not exist in datasets table
        rec = ExtractionRunResponse(
            run_id="run_fk_fail",
            dataset_id="nonexistent_ds",
            total_teams=0,
            total_members=0,
            teams=[],
        )
        with pytest.raises(IntegrityError):
            run_store.save(rec)

    def test_dataset_delete_restricted_by_foreign_key(self, migrated_test_db):
        ds_store = PostgresDatasetStore(engine=migrated_test_db)
        run_store = PostgresExtractionRunStore(engine=migrated_test_db)

        ds_store.save(DatasetRecord(dataset_id="ds_locked", filename="locked.csv", file_type="csv"))
        run_store.save(
            ExtractionRunResponse(
                run_id="run_locking",
                dataset_id="ds_locked",
                total_teams=0,
                total_members=0,
                teams=[],
            )
        )

        # Deleting dataset_id="ds_locked" should be restricted due to ondelete="RESTRICT"
        with pytest.raises(IntegrityError):
            ds_store.delete("ds_locked")


# ===========================================================================
# 4. Storage Factory Dataset & Extraction Run Tests
# ===========================================================================


class TestStorageFactoryDatasetExtraction:
    def test_factory_backend_selection(self, migrated_test_db):
        # Memory backend
        mem_factory = StorageFactory(backend="memory")
        assert "InMemoryDatasetStore" in type(mem_factory.get_dataset_store()).__name__
        assert "InMemoryExtractionRunStore" in type(mem_factory.get_extraction_run_store()).__name__

        # Postgres backend
        pg_factory = StorageFactory(backend="postgres", engine=migrated_test_db)
        pg_ds = pg_factory.get_dataset_store()
        pg_run = pg_factory.get_extraction_run_store()
        assert isinstance(pg_ds, PostgresDatasetStore)
        assert isinstance(pg_run, PostgresExtractionRunStore)
        assert pg_ds.engine == migrated_test_db
        assert pg_run.engine == migrated_test_db

    def test_factory_no_silent_fallback(self):
        bad_engine = sa.create_engine(
            "postgresql+psycopg://bad:bad@127.0.0.1:59999/bad_db?sslmode=disable",
            connect_args={"connect_timeout": 1},
        )
        factory = StorageFactory(backend="postgres", engine=bad_engine)
        store = factory.get_dataset_store()
        with pytest.raises((OperationalError, Exception)):
            store.get("any_id")


# ===========================================================================
# 5. API Workflows
# ===========================================================================


class TestDatasetExtractionAPIWorkflows:
    def test_upload_registration_file_persists_dataset(self, migrated_test_db):
        client = TestClient(app)
        csv_content = (
            "team_id,team_name,member_id,name,email,resume_url,github_url,linkedin_url,portfolio_url\n"
            "T1,Alpha,M1,Alice,alice@example.com,,,,\n"
            "T1,Alpha,M2,Bob,bob@example.com,,,,\n"
        )
        resp = client.post(
            "/api/ingestion/upload",
            files={"file": ("hackathon_teams.csv", io.BytesIO(csv_content.encode()), "text/csv")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        dataset_id = body.get("dataset_id")
        assert dataset_id is not None
        assert dataset_id.startswith("ds_")

        # Verify dataset was persisted in database
        ds_resp = client.get(f"/api/ingestion/datasets/{dataset_id}")
        assert ds_resp.status_code == 200
        ds_body = ds_resp.json()
        assert ds_body["dataset_id"] == dataset_id
        assert ds_body["filename"] == "hackathon_teams.csv"
        assert ds_body["file_type"] == "csv"
        assert ds_body["teams_count"] == 1
        assert ds_body["members_count"] == 2
        assert len(ds_body["payload"]["teams"]) == 1

        # Verify listing datasets includes it
        list_resp = client.get("/api/ingestion/datasets")
        assert list_resp.status_code == 200
        items = list_resp.json()
        assert any(item["dataset_id"] == dataset_id for item in items)

    def test_upload_invalid_file_does_not_persist(self, migrated_test_db):
        client = TestClient(app)
        # Empty CSV fails validation and produces success=False
        resp = client.post(
            "/api/ingestion/upload",
            files={"file": ("empty_teams.csv", io.BytesIO(b""), "text/csv")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert body.get("dataset_id") is None

        # Assert no datasets were created in the persistent store
        list_resp = client.get("/api/ingestion/datasets")
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 0

    def test_extract_signals_from_file_persists_both(self, migrated_test_db):
        client = TestClient(app)
        csv_data = (
            "team_id,team_name,member_id,name,Current CPI,College Year\n"
            "T1,Alpha,M1,Alice,8.8,3rd Year\n"
            "T1,Alpha,M2,Bob,9.2,2nd Year\n"
        )
        resp = client.post(
            "/api/signals/extract-file",
            files={"file": ("extract_teams.csv", io.BytesIO(csv_data.encode()), "text/csv")},
            data={
                "mapping": json.dumps({"Current CPI": "cgpa", "College Year": "academic_year"}),
                "selected_signals": "academic_cgpa,academic_year",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        run_id = body.get("run_id")
        dataset_id = body.get("dataset_id")
        assert run_id is not None
        assert dataset_id is not None

        # Verify dataset was persisted
        ds_resp = client.get(f"/api/ingestion/datasets/{dataset_id}")
        assert ds_resp.status_code == 200
        assert ds_resp.json()["dataset_id"] == dataset_id

        # Verify extraction run was persisted
        run_resp = client.get(f"/api/signals/runs/{run_id}")
        assert run_resp.status_code == 200
        run_body = run_resp.json()
        assert run_body["run_id"] == run_id
        assert run_body["dataset_id"] == dataset_id
        assert run_body["total_teams"] == 1
        assert run_body["total_members"] == 2

        # Verify listing runs with filter
        runs_list = client.get(f"/api/signals/runs?dataset_id={dataset_id}")
        assert runs_list.status_code == 200
        assert len(runs_list.json()) == 1
        assert runs_list.json()[0]["run_id"] == run_id

    def test_extract_signals_by_dataset_id(self, migrated_test_db):
        client = TestClient(app)
        # 1. Upload CSV to establish a dataset
        csv_content = (
            "team_id,team_name,member_id,name,email,cgpa,academic_year\n"
            "T1,Coders,M1,Charlie,charlie@example.com,9.0,3rd Year\n"
        )
        upload_resp = client.post(
            "/api/ingestion/upload",
            files={"file": ("dataset_test.csv", io.BytesIO(csv_content.encode()), "text/csv")},
        )
        assert upload_resp.status_code == 200
        dataset_id = upload_resp.json()["dataset_id"]

        # 2. Extract signals referencing dataset_id (teams omitted in request)
        extract_payload = {
            "dataset_id": dataset_id,
            "selected_signals": ["academic_cgpa", "academic_year"],
        }
        ext_resp = client.post("/api/signals/extract", json=extract_payload)
        assert ext_resp.status_code == 200
        ext_body = ext_resp.json()
        assert ext_body["dataset_id"] == dataset_id
        assert ext_body["total_teams"] == 1
        assert ext_body["total_members"] == 1
        assert ext_body["teams"][0]["team_id"] == "T1"
        assert ext_body["teams"][0]["member_results"][0]["signals"][0]["value"] == 9.0

        # Verify run was saved
        run_id = ext_body["run_id"]
        saved_run = client.get(f"/api/signals/runs/{run_id}")
        assert saved_run.status_code == 200
        assert saved_run.json()["dataset_id"] == dataset_id

    def test_extract_signals_missing_dataset_id_returns_404(self, migrated_test_db):
        client = TestClient(app)
        resp = client.post(
            "/api/signals/extract",
            json={"dataset_id": "nonexistent_dataset_id", "selected_signals": ["academic_cgpa"]},
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_get_nonexistent_dataset_returns_404(self, migrated_test_db):
        client = TestClient(app)
        resp = client.get("/api/ingestion/datasets/ds_does_not_exist")
        assert resp.status_code == 404

    def test_get_nonexistent_extraction_run_returns_404(self, migrated_test_db):
        client = TestClient(app)
        resp = client.get("/api/signals/runs/run_does_not_exist")
        assert resp.status_code == 404

    def test_downstream_endpoints_propagate_dataset_and_extraction_run_id(self, migrated_test_db):
        client = TestClient(app)

        # Seed presets so default 'basic' rule config and 'default' scoring config exist in database
        seed_database_presets(migrated_test_db)

        # 1. Create a dataset and an extraction run
        ds_store = PostgresDatasetStore(engine=migrated_test_db)
        run_store = PostgresExtractionRunStore(engine=migrated_test_db)
        ds_store.save(DatasetRecord(dataset_id="ds_downstream", filename="downstream.csv", file_type="csv"))
        run_store.save(
            ExtractionRunResponse(
                run_id="run_downstream",
                dataset_id="ds_downstream",
                total_teams=1,
                total_members=1,
                teams=[],
            )
        )

        team_payload = {
            "team_id": "T1",
            "team_name": "Downstream Team",
            "members": [{"member_id": "M1", "name": "Alice", "email": "a@example.com"}],
        }

        # 2. Test Rules Evaluation propagation
        rules_payload = {
            "teams": [team_payload],
            "dataset_id": "ds_downstream",
            "extraction_run_id": "run_downstream",
        }
        rules_resp = client.post("/api/rules/evaluate", json=rules_payload)
        assert rules_resp.status_code == 200
        rules_data = rules_resp.json()
        assert rules_data["dataset_id"] == "ds_downstream"
        assert rules_data["extraction_run_id"] == "run_downstream"

        # 3. Test Scoring Evaluation propagation
        score_payload = {
            "teams": [team_payload],
            "dataset_id": "ds_downstream",
            "extraction_run_id": "run_downstream",
        }
        score_resp = client.post("/api/scoring/evaluate", json=score_payload)
        assert score_resp.status_code == 200
        score_data = score_resp.json()
        assert score_data["dataset_id"] == "ds_downstream"
        assert score_data["extraction_run_id"] == "run_downstream"

        # 4. Test Ranking Evaluation propagation
        rank_payload = {
            "scoring_results": [
                {
                    "team_id": "T1",
                    "team_name": "Downstream Team",
                    "eligibility_status": "ELIGIBLE",
                    "final_score": 88.0,
                    "score_status": "CALCULATED",
                }
            ],
            "top_x": 1,
            "dataset_id": "ds_downstream",
            "extraction_run_id": "run_downstream",
        }
        rank_resp = client.post("/api/ranking/evaluate", json=rank_payload)
        assert rank_resp.status_code == 200
        rank_data = rank_resp.json()
        assert rank_data["dataset_id"] == "ds_downstream"
        assert rank_data["extraction_run_id"] == "run_downstream"
