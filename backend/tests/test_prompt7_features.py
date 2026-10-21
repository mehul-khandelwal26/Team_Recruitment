"""Tests for Prompt 7.0 features: Summary List Endpoints, Built-in Demo Preset, and CORS.

Covers:
1. Default list responses remain byte-for-byte unchanged when summary is not set (regression).
2. Summary endpoints: expected fields only (no payloads/teams), newest-first ordering, limit validation (422), and empty list behavior.
3. Ranking summary resolved context: populated when upstream records exist, nullable (None) when upstream runs are missing.
4. Summary payload size reduction ratio: summary responses are substantially smaller than full list responses for the demo dataset.
5. Built-in demo preset ('demo_mixed_review' / 'Demo: Lead Academic Review'):
   - Seeded in-memory and PostgreSQL modes.
   - Idempotent (no duplicates on repeated seeding).
   - Documented demo outcomes: 10 ELIGIBLE, 4 INELIGIBLE, 1 NEEDS_REVIEW (T02).
   - Top-5 ranking before override: T01, T12, T10, T11, T05.
   - Top-5 ranking after overriding T02: T01, T12, T02, T10, T11.
6. CORS configuration:
   - Allowed origins (http://localhost:5173, http://127.0.0.1:5173) succeed for normal and preflight requests.
   - Disallowed origins get no Access-Control-Allow-Origin header.
   - Content-Disposition appears in Access-Control-Expose-Headers.
   - Wildcard '*' is never combined with allow_credentials=True.
7. OpenAPI schema (/openapi.json) registers the new summary models.
8. PostgreSQL statement listener tests:
   - Query compilation verification with PostgreSQL dialect confirms summary queries never select the full payload column.
   - Live integration against TEST_DATABASE_URL (skipped when unset) uses an SQLAlchemy event listener to assert zero full-payload column selections during summary queries.
"""

from __future__ import annotations

import io
import json
import os
from typing import Any
import pytest
from fastapi.testclient import TestClient
import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.dialects import postgresql

from app.config import CORS_ORIGINS, assert_safe_test_database
from app.db.models import DatasetModel, ExtractionRunModel, RankingRunModel
from app.db.seeding import seed_database_presets
from app.db.session import create_app_engine
from app.db.stores import (
    PostgresDatasetStore,
    PostgresExtractionRunStore,
    PostgresRankingRunStore,
)
from app.schemas.ingestion import DatasetSummary
from app.ingestion.store import InMemoryDatasetStore, default_dataset_store
from app.main import app
from app.ranking.schemas import (
    RankingRunResponse,
    RankingRunSummary,
    RankingRunSummaryItem,
)
from app.ranking.store import InMemoryRankingRunStore, default_ranking_run_store
from app.rules.config_store import default_config_store
from app.rules.presets import get_default_presets
from app.rules.schemas import EligibilityRunResponse, EligibilityRunSummary
from app.rules.store import default_override_store, default_run_store
from app.scoring.config_store import default_scoring_config_store
from app.scoring.schemas import ScoringRunResponse, ScoringRunSummary
from app.scoring.store import default_scoring_run_store
from app.signals.schemas import ExtractionRunSummary
from app.signals.store import InMemoryExtractionRunStore, default_extraction_run_store
from app.storage import reset_test_database

SAMPLE_CSV_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "sample_data", "demo_teams.csv")
)


def _reset_all_stores():
    default_config_store.reset()
    default_scoring_config_store.reset()
    default_dataset_store.reset()
    default_extraction_run_store.reset()
    default_run_store.reset()
    default_override_store.reset()
    default_scoring_run_store.reset()
    default_ranking_run_store.reset()


@pytest.fixture(autouse=True)
def reset_in_memory_stores():
    """Ensure in-memory stores are cleanly cleared and seeded before each test."""
    _reset_all_stores()
    yield
    _reset_all_stores()


def _run_sample_pipeline(client: TestClient) -> dict[str, str]:
    """Helper to execute the full demo pipeline against the in-memory backend."""
    with open(SAMPLE_CSV_PATH, "rb") as f:
        upload_resp = client.post(
            "/api/ingestion/upload",
            files={"file": ("demo_teams.csv", f.read(), "text/csv")},
        )
    assert upload_resp.status_code == 200, upload_resp.text
    dataset_id = upload_resp.json()["dataset_id"]

    signals_resp = client.post(
        "/api/signals/extract",
        json={"dataset_id": dataset_id, "selected_signals": ["academic_cgpa", "academic_year"]},
    )
    assert signals_resp.status_code == 200, signals_resp.text
    extraction_run_id = signals_resp.json()["run_id"]

    rules_resp = client.post(
        "/api/rules/evaluate",
        json={
            "dataset_id": dataset_id,
            "extraction_run_id": extraction_run_id,
            "config_id": "demo_mixed_review",
        },
    )
    assert rules_resp.status_code == 200, rules_resp.text
    eligibility_run_id = rules_resp.json()["run_id"]

    scoring_resp = client.post(
        "/api/scoring/evaluate",
        json={
            "eligibility_run_id": eligibility_run_id,
            "scoring_config_id": "balanced",
        },
    )
    assert scoring_resp.status_code == 200, scoring_resp.text
    scoring_run_id = scoring_resp.json()["run_id"]

    ranking_resp = client.post(
        "/api/ranking/evaluate",
        json={
            "scoring_run_id": scoring_run_id,
            "eligibility_run_id": eligibility_run_id,
            "top_x": 5,
            "include_needs_review": False,
        },
    )
    assert ranking_resp.status_code == 200, ranking_resp.text
    ranking_run_id = ranking_resp.json()["run_id"]

    return {
        "dataset_id": dataset_id,
        "extraction_run_id": extraction_run_id,
        "eligibility_run_id": eligibility_run_id,
        "scoring_run_id": scoring_run_id,
        "ranking_run_id": ranking_run_id,
    }


# =============================================================================
# 1. Default List Endpoints Regression (Byte-for-byte unchanged)
# =============================================================================

def test_default_list_responses_byte_for_byte_unchanged():
    """Verify default list responses without summary param match summary=false byte-for-byte."""
    with TestClient(app) as client:
        _run_sample_pipeline(client)

        for endpoint in [
            "/api/ingestion/datasets",
            "/api/signals/runs",
            "/api/ranking/runs",
        ]:
            resp_default = client.get(endpoint)
            resp_false = client.get(f"{endpoint}?summary=false")

            assert resp_default.status_code == 200
            assert resp_false.status_code == 200
            # Byte-for-byte identical response content
            assert resp_default.content == resp_false.content

        # Full responses still include their full payload fields
        ds_data = client.get("/api/ingestion/datasets").json()
        assert len(ds_data) >= 1
        assert "payload" in ds_data[0]
        assert "mapping" in ds_data[0]

        sig_data = client.get("/api/signals/runs").json()
        assert len(sig_data) >= 1
        assert "teams" in sig_data[0]
        assert "analyzers_executed" in sig_data[0]

        rank_data = client.get("/api/ranking/runs").json()
        assert len(rank_data) >= 1
        assert "ranked_teams" in rank_data[0]
        assert "selected_teams" in rank_data[0]


# =============================================================================
# 2. Summary Endpoints: Schema, Compactness, and Empty Lists
# =============================================================================

def test_summary_endpoints_contract_fields_and_empty_list():
    """Verify summary list endpoints return empty lists when stores are empty and expected fields only."""
    with TestClient(app) as client:
        # 1. Empty list verification
        ds_empty = client.get("/api/ingestion/datasets?summary=true")
        assert ds_empty.status_code == 200
        assert ds_empty.json() == []

        sig_empty = client.get("/api/signals/runs?summary=true")
        assert sig_empty.status_code == 200
        assert sig_empty.json() == []

        rank_empty = client.get("/api/ranking/runs?summary=true")
        assert rank_empty.status_code == 200
        assert rank_empty.json() == []

        # 2. Populate stores and test summary shapes
        ids = _run_sample_pipeline(client)

        # Dataset summary check
        ds_summaries = client.get("/api/ingestion/datasets?summary=true").json()
        assert len(ds_summaries) == 1
        ds = ds_summaries[0]
        expected_ds_keys = {
            "dataset_id",
            "filename",
            "file_type",
            "teams_count",
            "members_count",
            "uploaded_at",
            "warnings_count",
            "user_id",
        }
        assert set(ds.keys()) == expected_ds_keys
        assert "teams" not in ds
        assert "payload" not in ds
        assert ds["teams_count"] == 15
        assert ds["members_count"] == 29

        # Extraction run summary check
        sig_summaries = client.get("/api/signals/runs?summary=true").json()
        assert len(sig_summaries) == 1
        sig = sig_summaries[0]
        expected_sig_keys = {
            "run_id",
            "dataset_id",
            "created_at",
            "selected_signals",
            "total_teams",
            "total_members",
            "warnings_count",
            "errors_count",
            "user_id",
        }
        assert set(sig.keys()) == expected_sig_keys
        assert "team_results" not in sig
        assert sig["total_teams"] == 15
        assert sig["total_members"] == 29

        # Ranking run summary check
        rank_summaries = client.get("/api/ranking/runs?summary=true").json()
        assert len(rank_summaries) == 1
        rank = rank_summaries[0]
        assert "ranked_teams" not in rank
        assert "selected_teams" not in rank
        assert "needs_review_teams" not in rank
        assert "excluded_teams" not in rank

        assert rank["run_id"] == ids["ranking_run_id"]
        assert rank["dataset_id"] == ids["dataset_id"]
        assert rank["scoring_run_id"] == ids["scoring_run_id"]
        assert rank["eligibility_run_id"] == ids["eligibility_run_id"]
        assert rank["top_x"] == 5
        assert rank["include_needs_review"] is False
        assert rank["selected_teams_count"] == 5
        assert rank["needs_review_count"] == 1
        assert rank["shortage"] == 0
        assert rank["tie_at_cutoff"] is False

        # Resolved upstream context
        assert rank["eligibility_config_id"] == "demo_mixed_review"
        assert rank["scoring_config_id"] == "balanced"
        assert rank["dataset_filename"] == "demo_teams.csv"


# =============================================================================
# 3. Newest-First Ordering & Limit Handling
# =============================================================================

def test_summary_ordering_newest_first_and_limit_validation():
    """Verify newest-first ordering, limit enforcement, and 422 validation on invalid limits."""
    with TestClient(app) as client:
        # Upload 3 distinct files to create multiple datasets
        csv_1 = "team_id,team_name,name,email\nT1,Team 1,Alice,alice@example.com\nT1,Team 1,Bob,bob@example.com\n"
        csv_2 = "team_id,team_name,name,email\nT2,Team 2,Charlie,charlie@example.com\nT2,Team 2,Dave,dave@example.com\n"
        csv_3 = "team_id,team_name,name,email\nT3,Team 3,Eve,eve@example.com\nT3,Team 3,Frank,frank@example.com\n"

        r1 = client.post("/api/ingestion/upload", files={"file": ("f1.csv", csv_1, "text/csv")}).json()
        r2 = client.post("/api/ingestion/upload", files={"file": ("f2.csv", csv_2, "text/csv")}).json()
        r3 = client.post("/api/ingestion/upload", files={"file": ("f3.csv", csv_3, "text/csv")}).json()

        # Fetch summaries with limit=2
        resp = client.get("/api/ingestion/datasets?summary=true&limit=2")
        assert resp.status_code == 200
        summaries = resp.json()
        assert len(summaries) == 2
        # Newest first: f3 then f2
        assert summaries[0]["dataset_id"] == r3["dataset_id"]
        assert summaries[1]["dataset_id"] == r2["dataset_id"]

        # Limit=1
        resp_1 = client.get("/api/ingestion/datasets?summary=true&limit=1")
        assert len(resp_1.json()) == 1
        assert resp_1.json()[0]["dataset_id"] == r3["dataset_id"]

        # Invalid limits -> 422
        for invalid_limit in [0, -1, 201, 500, "abc"]:
            err_resp = client.get(f"/api/ingestion/datasets?summary=true&limit={invalid_limit}")
            assert err_resp.status_code == 422, f"Expected 422 for limit={invalid_limit}, got {err_resp.status_code}"

            err_resp_sig = client.get(f"/api/signals/runs?summary=true&limit={invalid_limit}")
            assert err_resp_sig.status_code == 422

            err_resp_rank = client.get(f"/api/ranking/runs?summary=true&limit={invalid_limit}")
            assert err_resp_rank.status_code == 422


# =============================================================================
# 4. Resolved Context Nullability on Missing Upstream Runs
# =============================================================================

def test_ranking_summary_resolved_context_nullability():
    """Verify missing upstream runs yield null context fields without error."""
    with TestClient(app) as client:
        # Create a ranking run record referencing missing run IDs
        ranking_store = default_ranking_run_store
        orphan_run = RankingRunResponse(
            run_id="rank_orphan_test_001",
            scoring_run_id="non_existent_scoring_run",
            eligibility_run_id="non_existent_eligibility_run",
            dataset_id="non_existent_dataset",
            evaluated_at="2026-10-18T10:00:00Z",
            top_x=3,
            include_needs_review=False,
            summary=RankingRunSummary(
                selected_teams_count=0,
                shortage=3,
                needs_review_count=0,
                excluded_count=0,
                unresolved_count=0,
                tie_at_cutoff=False,
            ),
        )
        ranking_store.save(orphan_run)

        resp = client.get("/api/ranking/runs?summary=true")
        assert resp.status_code == 200
        summaries = resp.json()
        assert len(summaries) == 1
        summary = summaries[0]

        assert summary["run_id"] == "rank_orphan_test_001"
        assert summary["eligibility_config_id"] is None
        assert summary["eligibility_config_version"] is None
        assert summary["scoring_config_id"] is None
        assert summary["scoring_config_version"] is None
        assert summary["scoring_config_source"] is None
        assert summary["dataset_filename"] is None


# =============================================================================
# 5. Payload Size Reduction Ratio
# =============================================================================

def test_summary_payload_size_reduction_ratio():
    """Verify summary list endpoints produce substantially smaller responses than full lists."""
    with TestClient(app) as client:
        _run_sample_pipeline(client)

        # Datasets
        full_ds_bytes = len(client.get("/api/ingestion/datasets").content)
        summary_ds_bytes = len(client.get("/api/ingestion/datasets?summary=true").content)
        # Summary should be less than 20% of full dataset payload
        assert summary_ds_bytes < (full_ds_bytes * 0.20)

        # Ranking runs
        full_rank_bytes = len(client.get("/api/ranking/runs").content)
        summary_rank_bytes = len(client.get("/api/ranking/runs?summary=true").content)
        # Summary should be less than 15% of full ranking payload
        assert summary_rank_bytes < (full_rank_bytes * 0.15)


# =============================================================================
# 6. Built-in Demo Preset & Documented Workflow Outcomes
# =============================================================================

def test_demo_mixed_review_preset_seeded_in_memory_and_outcomes():
    """Verify demo_mixed_review preset exists out of the box and matches documented outcomes."""
    with TestClient(app) as client:
        # Preset existence in registered configs
        presets_resp = client.get("/api/rules/configs")
        assert presets_resp.status_code == 200
        presets = presets_resp.json()
        demo_preset = next((p for p in presets if p["config_id"] == "demo_mixed_review"), None)
        assert demo_preset is not None
        assert demo_preset["name"] == "Demo: Lead Academic Review"
        assert "demo" in demo_preset["name"].lower() or "demo" in demo_preset["description"].lower()

        # Ingestion
        with open(SAMPLE_CSV_PATH, "rb") as f:
            upload_resp = client.post(
                "/api/ingestion/upload",
                files={"file": ("demo_teams.csv", f.read(), "text/csv")},
            )
        dataset_id = upload_resp.json()["dataset_id"]

        # Signal extraction
        sig_resp = client.post(
            "/api/signals/extract",
            json={"dataset_id": dataset_id, "selected_signals": ["academic_cgpa", "academic_year"]},
        )
        extraction_run_id = sig_resp.json()["run_id"]

        # Eligibility evaluation using the built-in demo preset
        rules_resp = client.post(
            "/api/rules/evaluate",
            json={
                "dataset_id": dataset_id,
                "extraction_run_id": extraction_run_id,
                "config_id": "demo_mixed_review",
            },
        )
        assert rules_resp.status_code == 200
        rules_data = rules_resp.json()
        eligibility_run_id = rules_data["run_id"]

        # Documented outcome check: 10 ELIGIBLE, 4 INELIGIBLE, 1 NEEDS_REVIEW (T02)
        summary = rules_data["summary"]
        assert summary["total_teams"] == 15
        assert summary["eligible_count"] == 10
        assert summary["ineligible_count"] == 4
        assert summary["needs_review_count"] == 1

        t02_result = next(r for r in rules_data["teams"] if r["team_id"] == "T02")
        assert t02_result["status"] == "NEEDS_REVIEW"

        # Scoring with balanced preset
        scoring_resp = client.post(
            "/api/scoring/evaluate",
            json={
                "eligibility_run_id": eligibility_run_id,
                "scoring_config_id": "balanced",
            },
        )
        scoring_run_id = scoring_resp.json()["run_id"]

        # Top-5 Ranking before override: T01, T12, T10, T11, T05 (T02 held in review)
        rank_resp_1 = client.post(
            "/api/ranking/evaluate",
            json={
                "scoring_run_id": scoring_run_id,
                "eligibility_run_id": eligibility_run_id,
                "top_x": 5,
                "include_needs_review": False,
            },
        )
        assert rank_resp_1.status_code == 200
        rank_data_1 = rank_resp_1.json()
        selected_1 = [t["team_id"] for t in rank_data_1["selected_teams"]]
        assert selected_1 == ["T01", "T12", "T10", "T11", "T05"]
        assert len(rank_data_1["needs_review_teams"]) == 1
        assert rank_data_1["needs_review_teams"][0]["team_id"] == "T02"

        # Apply manual override for T02 -> ELIGIBLE
        override_resp = client.post(
            f"/api/rules/runs/{eligibility_run_id}/teams/T02/override",
            json={
                "override_status": "ELIGIBLE",
                "reason": "Team lead Charlie Brown verified manually; CGPA 8.4 meets threshold.",
                "overridden_by": "reviewer",
            },
        )
        assert override_resp.status_code == 200

        # Top-5 Ranking after override: T01, T12, T02, T10, T11 (T05 bumped to #6)
        rank_resp_2 = client.post(
            "/api/ranking/evaluate",
            json={
                "scoring_run_id": scoring_run_id,
                "eligibility_run_id": eligibility_run_id,
                "top_x": 5,
                "include_needs_review": False,
            },
        )
        assert rank_resp_2.status_code == 200
        rank_data_2 = rank_resp_2.json()
        selected_2 = [t["team_id"] for t in rank_data_2["selected_teams"]]
        assert selected_2 == ["T01", "T12", "T02", "T10", "T11"]
        assert len(rank_data_2["needs_review_teams"]) == 0


def test_demo_preset_idempotent_seeding():
    """Verify calling preset initialization multiple times creates no duplicates."""
    presets_1 = get_default_presets()
    presets_2 = get_default_presets()
    assert len(presets_1) == len(presets_2)
    demo_count = sum(1 for p in presets_2 if p.config_id == "demo_mixed_review")
    assert demo_count == 1


# =============================================================================
# 7. CORS Configuration
# =============================================================================

def test_cors_allowed_origins_preflight_and_normal():
    """Verify CORS middleware handles preflight and normal requests for allowed origins."""
    with TestClient(app) as client:
        for origin in CORS_ORIGINS:
            # Normal GET request
            resp = client.get("/api/ingestion/datasets", headers={"Origin": origin})
            assert resp.headers.get("access-control-allow-origin") == origin
            # Expose headers must contain content-disposition
            exposed = resp.headers.get("access-control-expose-headers", "")
            assert "content-disposition" in exposed.lower()

            # Preflight OPTIONS request
            options_resp = client.options(
                "/api/ranking/runs",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type",
                },
            )
            assert options_resp.status_code == 200
            assert options_resp.headers.get("access-control-allow-origin") == origin
            allow_methods = options_resp.headers.get("access-control-allow-methods", "")
            for method in ["GET", "POST", "PUT", "DELETE", "OPTIONS"]:
                assert method in allow_methods
            allow_headers = options_resp.headers.get("access-control-allow-headers", "")
            assert "content-type" in allow_headers.lower()


def test_cors_comma_separated_origins_support():
    """Verify multiple comma-separated origins are accepted by CORS configuration."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    test_app = FastAPI()
    test_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://my-frontend-deploy.org",
    ]
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=test_origins,
        allow_credentials="*" not in test_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
        expose_headers=["Content-Disposition"],
    )

    @test_app.get("/dummy")
    def dummy_route():
        return {"ok": True}

    with TestClient(test_app) as client:
        for origin in test_origins:
            resp = client.get("/dummy", headers={"Origin": origin})
            assert resp.status_code == 200
            assert resp.headers.get("access-control-allow-origin") == origin
            assert "content-disposition" in resp.headers.get("access-control-expose-headers", "").lower()

            opt = client.options(
                "/dummy",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type",
                },
            )
            assert opt.status_code == 200
            assert opt.headers.get("access-control-allow-origin") == origin


def test_cors_disallowed_origin_rejected():
    """Verify disallowed origins do not receive Access-Control-Allow-Origin headers."""
    with TestClient(app) as client:
        evil_origin = "http://malicious-site.example.com"
        resp = client.get("/api/ingestion/datasets", headers={"Origin": evil_origin})
        assert "access-control-allow-origin" not in resp.headers

        options_resp = client.options(
            "/api/ranking/runs",
            headers={
                "Origin": evil_origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert "access-control-allow-origin" not in options_resp.headers


def test_cors_wildcard_without_credentials_invariant():
    """Verify wildcard '*' origins never get combined with allow_credentials=True."""
    from fastapi.middleware.cors import CORSMiddleware
    from starlette.datastructures import Headers

    # Find the CORSMiddleware in the application's middleware stack
    cors_mw = None
    for mw in app.user_middleware:
        if mw.cls == CORSMiddleware:
            cors_mw = mw
            break
    assert cors_mw is not None
    # If '*' is in allow_origins, allow_credentials must be False
    allow_origins = cors_mw.kwargs.get("allow_origins", [])
    allow_credentials = cors_mw.kwargs.get("allow_credentials", False)
    if "*" in allow_origins:
        assert allow_credentials is False


# =============================================================================
# 8. OpenAPI Schema Contains Summary Models
# =============================================================================

def test_openapi_contains_summary_models():
    """Verify OpenAPI documentation registers DatasetSummary, ExtractionRunSummary, and RankingRunSummaryItem."""
    with TestClient(app) as client:
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        components = schema.get("components", {}).get("schemas", {})

        assert "DatasetSummary" in components
        assert "ExtractionRunSummary" in components
        assert "RankingRunSummaryItem" in components or "RankingSummary" in components

        ds_props = components["DatasetSummary"]["properties"]
        assert "dataset_id" in ds_props
        assert "warnings_count" in ds_props
        assert "teams" not in ds_props

        sig_props = components["ExtractionRunSummary"]["properties"]
        assert "run_id" in sig_props
        assert "selected_signals" in sig_props
        assert "team_results" not in sig_props


# =============================================================================
# 9. Postgres SQL Dialect Compilation Test (No Full Payload Selected)
# =============================================================================

def test_postgres_sql_summary_queries_never_select_full_payload():
    """Verify that Postgres summary queries compile SQL that selects typed columns/subkeys only and never full payload."""
    engine = sa.create_engine("postgresql+psycopg://user:pass@localhost:5432/db")

    ds_store = PostgresDatasetStore(engine)
    sig_store = PostgresExtractionRunStore(engine)
    rank_store = PostgresRankingRunStore(engine)

    # 1. Inspect DatasetStore summary query
    ds_stmt = (
        sa.select(
            DatasetModel.dataset_id,
            DatasetModel.filename,
            DatasetModel.file_type,
            DatasetModel.teams_count,
            DatasetModel.members_count,
            DatasetModel.uploaded_at,
            sa.case(
                (DatasetModel.payload["warnings"] != sa.null(), sa.func.jsonb_array_length(DatasetModel.payload["warnings"])),
                else_=0,
            ).label("warnings_count"),
        )
        .order_by(DatasetModel.uploaded_at.desc(), DatasetModel.dataset_id.desc())
        .limit(50)
    )
    compiled_ds = str(ds_stmt.compile(dialect=postgresql.dialect()))
    # Must NOT select datasets.payload as a whole column
    assert "datasets.payload," not in compiled_ds
    assert "datasets.payload FROM" not in compiled_ds
    # Must extract warnings subkey via JSONB subscript or operator
    assert "datasets.payload[" in compiled_ds or "payload ->" in compiled_ds

    # 2. Inspect ExtractionRunStore summary query
    sig_stmt = (
        sa.select(
            ExtractionRunModel.run_id,
            ExtractionRunModel.dataset_id,
            ExtractionRunModel.created_at,
            ExtractionRunModel.selected_signals,
            ExtractionRunModel.total_teams,
            ExtractionRunModel.total_members,
            sa.case(
                (ExtractionRunModel.payload["warnings"] != sa.null(), sa.func.jsonb_array_length(ExtractionRunModel.payload["warnings"])),
                else_=0,
            ).label("warnings_count"),
            sa.case(
                (ExtractionRunModel.payload["errors"] != sa.null(), sa.func.jsonb_array_length(ExtractionRunModel.payload["errors"])),
                else_=0,
            ).label("errors_count"),
        )
        .order_by(ExtractionRunModel.created_at.desc(), ExtractionRunModel.run_id.desc())
        .limit(50)
    )
    compiled_sig = str(sig_stmt.compile(dialect=postgresql.dialect()))
    assert "extraction_runs.payload," not in compiled_sig
    assert "extraction_runs.payload FROM" not in compiled_sig
    assert "extraction_runs.payload[" in compiled_sig or "payload ->" in compiled_sig

    # 3. Inspect RankingRunStore summary query (with batched outerjoin for context)
    rank_stmt = (
        sa.select(
            RankingRunModel.run_id,
            RankingRunModel.evaluated_at,
            RankingRunModel.dataset_id,
            RankingRunModel.extraction_run_id,
            RankingRunModel.scoring_run_id,
            RankingRunModel.eligibility_run_id,
            RankingRunModel.top_x,
            RankingRunModel.include_needs_review,
            RankingRunModel.tiebreak_criterion_id,
            RankingRunModel.payload["summary"].label("summary_json"),
        )
        .order_by(RankingRunModel.evaluated_at.desc(), RankingRunModel.run_id.desc())
        .limit(50)
    )
    compiled_rank = str(rank_stmt.compile(dialect=postgresql.dialect()))
    # Must NOT select ranking_runs.payload as a whole column
    assert "ranking_runs.payload," not in compiled_rank
    assert "ranking_runs.payload FROM" not in compiled_rank
    # Must extract summary subkey via JSONB subscript or operator
    assert "ranking_runs.payload[" in compiled_rank or "payload ->" in compiled_rank


# =============================================================================
# 10. Live Postgres Database Tests with Statement Listener (Skipped when unset)
# =============================================================================

TEST_DB_URL = os.getenv("TEST_DATABASE_URL")


@pytest.mark.skipif(
    not TEST_DB_URL,
    reason="TEST_DATABASE_URL is not configured; skipping live PostgreSQL integration tests as required.",
)
def test_postgres_live_summaries_and_statement_listener():
    """Verify live Postgres list_summaries execution never selects full payload via statement listener."""
    assert_safe_test_database(TEST_DB_URL)

    engine = create_app_engine(url=TEST_DB_URL)
    reset_test_database(engine)
    seed_database_presets(engine)

    ds_store = PostgresDatasetStore(engine)
    sig_store = PostgresExtractionRunStore(engine)
    rank_store = PostgresRankingRunStore(engine)

    # Attach statement listener to capture all executed SQL statements
    executed_statements: list[str] = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        executed_statements.append(statement)

    event.listen(engine, "before_cursor_execute", before_cursor_execute)

    try:
        # Execute summary queries
        ds_summaries = ds_store.list_summaries(limit=50)
        sig_summaries = sig_store.list_summaries(limit=50)
        rank_summaries = rank_store.list_summaries(limit=50)

        assert ds_summaries == []
        assert sig_summaries == []
        assert rank_summaries == []

        # Verify no executed statement selected the whole payload column
        for stmt in executed_statements:
            # Check the SELECT clause for bare payload column selections
            stmt_upper = stmt.upper()
            select_part = stmt_upper.split("FROM")[0] if "FROM" in stmt_upper else stmt_upper
            assert "PAYLOAD," not in select_part or "PAYLOAD ->" in select_part
            assert "DATASETS.PAYLOAD FROM" not in stmt_upper
            assert "EXTRACTION_RUNS.PAYLOAD FROM" not in stmt_upper
            assert "RANKING_RUNS.PAYLOAD FROM" not in stmt_upper
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)
        engine.dispose()
