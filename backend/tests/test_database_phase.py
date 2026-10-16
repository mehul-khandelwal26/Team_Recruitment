"""Tests for Database Phase Stages 1-2.

Covers:
1. normalize_database_url: scheme normalization, sslmode enforcement, query param preservation, secret safety.
2. assert_safe_test_database: isolation validation, rejection of identical or overlapping host/db, secret safety.
3. Startup and production safety: lifespan validation (not at import), case-insensitivity, health endpoint.
4. Optional model fields and endpoint labeling: config_source and config_snapshot handling for inline vs stored.
5. Payload-to-columns helpers: all 8 table helpers, typed column derivation, handling missing optional values.
6. Alembic migration integration test: strictly conditioned on TEST_DATABASE_URL, verifying tables and constraints.
"""

from __future__ import annotations

import os
from typing import Any
import pytest
from fastapi.testclient import TestClient

from app.config import (
    assert_safe_test_database,
    normalize_database_url,
    validate_startup_configuration,
)
from app.db.models import (
    derive_dataset_columns,
    derive_eligibility_run_columns,
    derive_extraction_run_columns,
    derive_manual_override_columns,
    derive_ranking_run_columns,
    derive_rule_configuration_columns,
    derive_scoring_configuration_columns,
    derive_scoring_run_columns,
)
from app.main import app
from app.ranking.schemas import RankingEvaluationRequest, RankingRunResponse
from app.rules.schemas import EligibilityRunResponse, RuleConfiguration
from app.scoring.config_store import default_scoring_config_store
from app.scoring.schemas import (
    EvaluationCriterion,
    ScoringConfiguration,
    ScoringEvaluationRequest,
    ScoringRunResponse,
)
from app.signals.schemas import ExtractionRunResponse

client = TestClient(app)


# ===========================================================================
# 1. Database URL Normalization Tests
# ===========================================================================


class TestNormalizeDatabaseUrl:
    def test_schemes_normalized_to_psycopg(self):
        url1 = "postgresql://user:secret123@neon.tech:5432/mydb"
        norm1 = normalize_database_url(url1)
        assert norm1.startswith("postgresql+psycopg://")
        assert "sslmode=require" in norm1

        url2 = "postgres://user:secret123@neon.tech:5432/mydb"
        norm2 = normalize_database_url(url2)
        assert norm2.startswith("postgresql+psycopg://")
        assert "sslmode=require" in norm2

        url3 = "postgresql+psycopg://user:secret123@neon.tech:5432/mydb"
        norm3 = normalize_database_url(url3)
        assert norm3.startswith("postgresql+psycopg://")
        assert "sslmode=require" in norm3

    def test_sslmode_preservation_and_no_duplication(self):
        url_with_ssl = "postgresql://user:pass@host:5432/db?sslmode=require"
        norm = normalize_database_url(url_with_ssl)
        assert norm.count("sslmode=") == 1
        assert "sslmode=require" in norm

        url_with_custom_ssl = "postgresql://user:pass@host:5432/db?sslmode=verify-full"
        norm_custom = normalize_database_url(url_with_custom_ssl)
        assert norm_custom.count("sslmode=") == 1
        assert "sslmode=verify-full" in norm_custom

    def test_query_parameters_preserved(self):
        url = "postgresql://user:pass@host:5432/db?channel_binding=require&options=-c%20search_path%3Dpublic"
        norm = normalize_database_url(url)
        assert "channel_binding=require" in norm
        assert "sslmode=require" in norm
        assert "search_path" in norm

    def test_error_does_not_leak_url_or_credentials(self):
        secret_url = "mysql://admin:SuperSecretPassword99@localhost/secret_db"
        with pytest.raises(ValueError) as exc_info:
            normalize_database_url(secret_url)

        msg = str(exc_info.value)
        assert "SuperSecretPassword99" not in msg
        assert "secret_db" not in msg
        assert "mysql://" not in msg

        with pytest.raises(ValueError) as empty_exc:
            normalize_database_url("")
        assert "Invalid database URL" in str(empty_exc.value)


# ===========================================================================
# 2. Test Database Safety Assertion Tests
# ===========================================================================


class TestAssertSafeTestDatabase:
    def test_reject_when_test_db_url_unset(self, monkeypatch):
        monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
        with pytest.raises(ValueError) as exc:
            assert_safe_test_database("postgresql://user:pass@localhost:5432/test_db")
        assert "TEST_DATABASE_URL is not configured" in str(exc.value)
        assert "password" not in str(exc.value)

    def test_reject_when_supplied_url_differs_from_configured_test_url(self, monkeypatch):
        monkeypatch.setenv("TEST_DATABASE_URL", "postgresql://u:p@test-host:5432/test_db")
        with pytest.raises(ValueError) as exc:
            assert_safe_test_database("postgresql://u:p@other-host:5432/test_db")
        assert "Supplied URL does not match configured TEST_DATABASE_URL" in str(exc.value)
        assert "other-host" not in str(exc.value)

    def test_reject_when_identical_to_database_url(self, monkeypatch):
        url = "postgresql://u:p@db-host:5432/prod_db"
        monkeypatch.setenv("DATABASE_URL", url)
        monkeypatch.setenv("TEST_DATABASE_URL", url)
        with pytest.raises(ValueError) as exc:
            assert_safe_test_database(url)
        assert "TEST_DATABASE_URL cannot be identical to DATABASE_URL" in str(exc.value)
        assert "prod_db" not in str(exc.value)

    def test_reject_when_same_host_and_database_name(self, monkeypatch):
        dev_url = "postgresql://dev_user:dev_pass@ep-cool-123.us-east-2.neon.tech:5432/recruitment_db"
        test_url = "postgresql+psycopg://test_user:test_pass@ep-cool-123.us-east-2.neon.tech:5432/recruitment_db"
        monkeypatch.setenv("DATABASE_URL", dev_url)
        monkeypatch.setenv("TEST_DATABASE_URL", test_url)
        with pytest.raises(ValueError) as exc:
            assert_safe_test_database(test_url)
        assert "cannot share the same host and database name" in str(exc.value)
        assert "ep-cool-123" not in str(exc.value)
        assert "recruitment_db" not in str(exc.value)

    def test_allow_when_database_url_unset(self, monkeypatch):
        test_url = "postgresql://test_u:test_p@isolated-host:5432/isolated_test_db"
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("TEST_DATABASE_URL", test_url)
        # Should not raise
        assert_safe_test_database(test_url)

    def test_allow_when_valid_separate_database(self, monkeypatch):
        dev_url = "postgresql://user:pass@neon-branch-main.tech:5432/app_db"
        test_url = "postgresql://user:pass@neon-branch-test.tech:5432/test_db"
        monkeypatch.setenv("DATABASE_URL", dev_url)
        monkeypatch.setenv("TEST_DATABASE_URL", test_url)
        # Should not raise
        assert_safe_test_database(test_url)


# ===========================================================================
# 3. Startup and Production Safety Tests
# ===========================================================================


class TestStartupProductionSafety:
    def test_production_without_postgres_storage_fails_at_startup(self, monkeypatch):
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("STORAGE_BACKEND", "memory")
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")

        with pytest.raises(RuntimeError) as exc:
            validate_startup_configuration()
        assert "In production, STORAGE_BACKEND must be set to 'postgres'" in str(exc.value)

    def test_production_case_insensitive_env_check(self, monkeypatch):
        for variant in ("PRODUCTION", "Production", "pRoDuCtIoN"):
            monkeypatch.setenv("APP_ENV", variant)
            monkeypatch.setenv("STORAGE_BACKEND", "memory")
            with pytest.raises(RuntimeError):
                validate_startup_configuration()

    def test_production_without_database_url_fails_at_startup(self, monkeypatch):
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("STORAGE_BACKEND", "postgres")
        monkeypatch.delenv("DATABASE_URL", raising=False)

        with pytest.raises(RuntimeError) as exc:
            validate_startup_configuration()
        assert "In production, DATABASE_URL must be configured" in str(exc.value)

    def test_development_defaults_to_memory_without_raising(self, monkeypatch):
        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.setenv("STORAGE_BACKEND", "memory")
        monkeypatch.delenv("DATABASE_URL", raising=False)
        # Should execute cleanly without error
        validate_startup_configuration()

    def test_health_check_returns_storage_backend(self):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert "environment" in body
        assert "version" in body
        assert body["storage_backend"] == "memory"


# ===========================================================================
# 4. Optional Model Fields and Endpoint Labeling Tests
# ===========================================================================


class TestOptionalModelFieldsAndEndpointLabeling:
    def test_optional_fields_default_none_on_response_models(self):
        elig_run = EligibilityRunResponse(
            run_id="test_run",
            config_id="basic",
            config_version=1,
            evaluated_at="2026-10-17T00:00:00Z",
        )
        assert elig_run.dataset_id is None
        assert elig_run.extraction_run_id is None

        score_run = ScoringRunResponse(
            run_id="test_score",
            config_id="balanced",
            config_version=1,
            evaluated_at="2026-10-17T00:00:00Z",
            teams=[],
            summary={"total_teams": 0},
        )
        assert score_run.eligibility_run_id is None
        assert score_run.dataset_id is None
        assert score_run.extraction_run_id is None
        assert score_run.config_source is None
        assert score_run.config_snapshot is None

        rank_run = RankingRunResponse(
            run_id="test_rank",
            evaluated_at="2026-10-17T00:00:00Z",
            top_x=5,
        )
        assert rank_run.dataset_id is None
        assert rank_run.extraction_run_id is None

        extract_run = ExtractionRunResponse(
            run_id="test_ext",
            teams=[],
        )
        assert extract_run.dataset_id is None
        assert extract_run.created_at is None or isinstance(extract_run.created_at, str)

    def test_scoring_evaluate_stored_config_source_labeling(self):
        sample_team = {
            "team_id": "T1",
            "team_name": "Alpha",
            "members": [{"member_id": "M1", "name": "Alice"}],
        }
        req = {
            "teams": [sample_team],
            "config_id": "balanced",
        }
        resp = client.post("/api/scoring/evaluate", json=req)
        assert resp.status_code == 200
        body = resp.json()
        assert body["config_source"] == "stored"
        assert body["config_snapshot"] is None
        assert body["dataset_id"] is None
        assert body["extraction_run_id"] is None

    def test_scoring_evaluate_inline_config_source_and_snapshot_labeling(self):
        sample_team = {
            "team_id": "T1",
            "team_name": "Alpha",
            "members": [{"member_id": "M1", "name": "Alice"}],
        }
        # Inline config reusing the ID 'balanced' to test ambiguity resolution
        inline_cfg = {
            "config_id": "balanced",
            "name": "Custom Inline Balanced",
            "version": 1,
            "criteria": [
                {
                    "criterion_id": "repos",
                    "name": "Public Repos",
                    "target_signal_key": "github_public_repo_count",
                    "criterion_type": "numeric_range",
                    "weight": 1.0,
                    "normalization": {
                        "linear_range": {"min_value": 0.0, "max_value": 10.0}
                    },
                }
            ],
        }
        req = {
            "teams": [sample_team],
            "inline_config": inline_cfg,
        }
        resp = client.post("/api/scoring/evaluate", json=req)
        assert resp.status_code == 200
        body = resp.json()
        assert body["config_source"] == "inline"
        assert body["config_snapshot"] is not None
        assert body["config_snapshot"]["name"] == "Custom Inline Balanced"

    def test_ranking_option_c_config_source_labeling(self):
        sample_team = {
            "team_id": "T1",
            "team_name": "Alpha",
            "members": [{"member_id": "M1", "name": "Alice"}],
        }
        inline_cfg = {
            "config_id": "balanced",
            "name": "Inline Option C Config",
            "version": 1,
            "criteria": [
                {
                    "criterion_id": "repos",
                    "name": "Public Repos",
                    "target_signal_key": "github_public_repo_count",
                    "criterion_type": "numeric_range",
                    "weight": 1.0,
                    "normalization": {
                        "linear_range": {"min_value": 0.0, "max_value": 10.0}
                    },
                }
            ],
        }
        req = {
            "top_x": 1,
            "teams": [sample_team],
            "inline_scoring_config": inline_cfg,
        }
        resp = client.post("/api/ranking/evaluate", json=req)
        assert resp.status_code == 200
        rank_body = resp.json()
        assert rank_body["scoring_run_id"] is not None

        # Retrieve the generated scoring run to verify config_source and snapshot were persisted
        score_resp = client.get(f"/api/scoring/runs/{rank_body['scoring_run_id']}")
        assert score_resp.status_code == 200
        score_body = score_resp.json()
        assert score_body["config_source"] == "inline"
        assert score_body["config_snapshot"] is not None
        assert score_body["config_snapshot"]["name"] == "Inline Option C Config"


# ===========================================================================
# 5. Payload-to-Columns Helpers Tests
# ===========================================================================


class TestPayloadToColumnsHelpers:
    def test_derive_rule_configuration_columns(self):
        payload = {
            "config_id": "basic",
            "version": 2,
            "name": "Basic Rules V2",
            "description": "Updated basic rules",
            "is_active": True,
            "created_at": "2026-10-16T12:00:00Z",
            "updated_at": "2026-10-16T12:30:00Z",
            "rules": [],
        }
        derived = derive_rule_configuration_columns(payload)
        assert derived["config_id"] == "basic"
        assert derived["version"] == 2
        assert derived["name"] == "Basic Rules V2"
        assert derived["is_active"] is True
        assert derived["payload"] == payload

    def test_derive_dataset_columns(self):
        payload = {
            "success": True,
            "teams_count": 5,
            "members_count": 15,
            "teams": [],
            "warnings": [],
            "unmapped_fields": [],
        }
        derived = derive_dataset_columns(
            payload,
            dataset_id="ds_12345",
            filename="teams.csv",
            file_type="csv",
            mapping={"col1": "name"},
        )
        assert derived["dataset_id"] == "ds_12345"
        assert derived["filename"] == "teams.csv"
        assert derived["file_type"] == "csv"
        assert derived["teams_count"] == 5
        assert derived["members_count"] == 15
        assert derived["mapping"] == {"col1": "name"}
        assert derived["payload"] == payload

    def test_derive_extraction_run_columns(self):
        payload = {
            "run_id": "ext_999",
            "dataset_id": "ds_12345",
            "total_teams": 3,
            "total_members": 9,
            "selected_signals": ["github_public_repo_count"],
            "analyzers_executed": ["github_analyzer"],
            "created_at": "2026-10-16T14:00:00Z",
        }
        derived = derive_extraction_run_columns(payload)
        assert derived["run_id"] == "ext_999"
        assert derived["dataset_id"] == "ds_12345"
        assert derived["total_teams"] == 3
        assert derived["total_members"] == 9
        assert derived["selected_signals"] == ["github_public_repo_count"]

    def test_derive_eligibility_run_columns(self):
        payload = {
            "run_id": "elig_1",
            "config_id": "basic",
            "config_version": 1,
            "evaluated_at": "2026-10-16T15:00:00Z",
            "summary": {
                "total_teams": 10,
                "eligible_count": 7,
                "ineligible_count": 2,
                "needs_review_count": 1,
            },
            "dataset_id": None,
            "extraction_run_id": None,
        }
        derived = derive_eligibility_run_columns(payload)
        assert derived["run_id"] == "elig_1"
        assert derived["config_id"] == "basic"
        assert derived["total_teams"] == 10
        assert derived["eligible_count"] == 7
        assert derived["dataset_id"] is None
        assert derived["extraction_run_id"] is None

    def test_derive_manual_override_columns(self):
        payload = {
            "override_id": "ovr_1",
            "run_id": "elig_1",
            "team_id": "T1",
            "original_status": "INELIGIBLE",
            "override_status": "ELIGIBLE",
            "reason": "Special organizer approval",
            "overridden_by": "lead_organizer",
            "overridden_at": "2026-10-16T15:30:00Z",
        }
        derived = derive_manual_override_columns(payload)
        assert derived["override_id"] == "ovr_1"
        assert derived["run_id"] == "elig_1"
        assert derived["team_id"] == "T1"
        assert derived["original_status"] == "INELIGIBLE"
        assert derived["override_status"] == "ELIGIBLE"
        assert derived["reason"] == "Special organizer approval"

    def test_derive_scoring_configuration_columns(self):
        payload = {
            "config_id": "balanced",
            "name": "Balanced Rubric",
            "version": 1,
            "scale_max": 100.0,
            "score_ineligible_teams": True,
            "is_active": True,
        }
        derived = derive_scoring_configuration_columns(payload)
        assert derived["config_id"] == "balanced"
        assert derived["version"] == 1
        assert derived["scale_max"] == 100.0
        assert derived["score_ineligible_teams"] is True

    def test_derive_scoring_run_columns(self):
        payload = {
            "run_id": "score_1",
            "config_id": "balanced",
            "config_version": 1,
            "config_source": "inline",
            "eligibility_run_id": "elig_1",
            "evaluated_at": "2026-10-16T16:00:00Z",
            "summary": {
                "total_teams": 8,
                "calculated_teams": 8,
                "average_score": 74.5,
            },
        }
        derived = derive_scoring_run_columns(payload)
        assert derived["run_id"] == "score_1"
        assert derived["config_source"] == "inline"
        assert derived["eligibility_run_id"] == "elig_1"
        assert derived["average_score"] == 74.5
        assert derived["dataset_id"] is None

    def test_derive_ranking_run_columns(self):
        payload = {
            "run_id": "rank_1",
            "scoring_run_id": "score_1",
            "eligibility_run_id": "elig_1",
            "top_x": 5,
            "include_needs_review": False,
            "evaluated_at": "2026-10-16T16:30:00Z",
            "summary": {
                "selected_teams_count": 5,
                "shortage": 0,
                "cutoff_score": 82.0,
            },
        }
        derived = derive_ranking_run_columns(payload)
        assert derived["run_id"] == "rank_1"
        assert derived["scoring_run_id"] == "score_1"
        assert derived["top_x"] == 5
        assert derived["selected_count"] == 5
        assert derived["shortage"] == 0
        assert derived["cutoff_score"] == 82.0
        assert derived["dataset_id"] is None


# ===========================================================================
# 6. Alembic Migration Integration Test
# ===========================================================================


class TestAlembicMigrationIntegration:
    """Verifies Alembic migrations against an isolated test database.

    Strictly skipped unless TEST_DATABASE_URL is set in environment.
    """

    @pytest.mark.skipif(
        not os.getenv("TEST_DATABASE_URL"),
        reason="TEST_DATABASE_URL not configured; skipping live migration test as required.",
    )
    def test_alembic_upgrade_and_downgrade(self):
        test_db_url = os.environ["TEST_DATABASE_URL"]
        assert_safe_test_database(test_db_url)

        from alembic import command
        from alembic.config import Config
        from sqlalchemy import inspect
        from app.db.session import create_app_engine

        ini_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
        alembic_cfg = Config(ini_path)
        alembic_cfg.attributes["override_url"] = test_db_url

        # Execute migration upgrade
        command.upgrade(alembic_cfg, "head")

        engine = create_app_engine(url=test_db_url)
        with engine.connect() as conn:
            inspector = inspect(conn)
            tables = set(inspector.get_table_names())
            expected_tables = {
                "rule_configurations",
                "scoring_configurations",
                "datasets",
                "extraction_runs",
                "eligibility_runs",
                "manual_overrides",
                "scoring_runs",
                "ranking_runs",
            }
            assert expected_tables.issubset(tables)

            # Inspect foreign key delete rules
            elig_fks = inspector.get_foreign_keys("eligibility_runs")
            rule_fk = next(fk for fk in elig_fks if fk["referred_table"] == "rule_configurations")
            assert (rule_fk.get("options") or {}).get("ondelete", "RESTRICT").upper() == "RESTRICT"

            override_fks = inspector.get_foreign_keys("manual_overrides")
            elig_override_fk = next(fk for fk in override_fks if fk["referred_table"] == "eligibility_runs")
            assert (elig_override_fk.get("options") or {}).get("ondelete", "").upper() == "CASCADE"

        # Execute migration downgrade
        command.downgrade(alembic_cfg, "base")

        with engine.connect() as conn:
            inspector = inspect(conn)
            remaining_tables = set(inspector.get_table_names())
            for t in expected_tables:
                assert t not in remaining_tables
