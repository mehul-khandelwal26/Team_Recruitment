"""Automated test suite for Database Phase Prompt 5 features.

Covers:
1. Reset Guard (A):
   - Calling reset() with default app engine raises ValueError and deletes nothing.
   - Calling reset() with an injected validated TEST_DATABASE_URL engine works.
2. ID-Only Mode & Provenance Inheritance (B):
   - Rules evaluate with dataset_id and extraction_run_id (no inline teams/signals).
   - Rules evaluate 404 for missing dataset_id or extraction_run_id.
   - Rules evaluate 400 for mismatched dataset_id between request and extraction run.
   - Scoring evaluate ID-only mode and 404/400 validation.
   - Provenance inheritance: scoring run inherits dataset_id & extraction_run_id from eligibility_run.
   - Explicit dataset_id is preserved and not overwritten during inheritance.
   - Ranking evaluate Option C ID-only mode with dataset_id and extraction_run_id.
   - End-to-end ID-only pipeline against TEST_DATABASE_URL (skipped if unset).
3. Backward Compatibility (Payload Mode):
   - Existing payload requests with inline teams and signals continue to work unchanged.
4. CSV Export (C):
   - GET /api/ranking/runs/{run_id}/export returns text/csv, UTF-8 with BOM (\xef\xbb\xbf).
   - Filename in Content-Disposition contains run_id.
   - 404 for unknown run_id.
   - Row ordering: selected -> other ranked -> needs_review -> unresolved -> excluded.
   - Column schema validation and criteria_evaluated format ("X of Y").
   - CSV formula injection mitigation ('=', '+', '-', '@' prefixed with single quote).
5. Sample Data Validation (D):
   - demo_teams.csv executes cleanly through the pipeline matching sample_data/README.md.
"""

from __future__ import annotations

import io
import os
from typing import Any
import pytest
from fastapi.testclient import TestClient
import sqlalchemy as sa

from app.api.endpoints.ranking import export_ranking_run_csv
from app.config import TEST_DATABASE_URL, assert_safe_test_database
from app.db.session import create_app_engine
from app.db.stores import (
    PostgresDatasetStore,
    PostgresEligibilityRunStore,
    PostgresExtractionRunStore,
    PostgresRankingRunStore,
    PostgresRuleConfigStore,
    PostgresScoringConfigStore,
    PostgresScoringRunStore,
)
from app.ingestion.parser import parse_csv
from app.ingestion.store import default_dataset_store
from app.main import app
from app.ranking.schemas import (
    ExcludedTeamResult,
    ExclusionReason,
    RankedTeamResult,
    RankingEvaluationRequest,
    RankingRunResponse,
    SelectionStatus,
)
from app.ranking.store import default_ranking_run_store
from app.rules.config_store import default_config_store
from app.rules.schemas import (
    EligibilityEvaluateRequest,
    EligibilityRunResponse,
    EligibilityStatus,
    TeamEligibilityResult,
)
from app.rules.store import default_run_store
from app.schemas.ingestion import DatasetRecord
from app.scoring.config_store import default_scoring_config_store
from app.scoring.schemas import (
    ScoreStatus,
    ScoringEvaluationRequest,
    ScoringRunResponse,
    TeamScoringResult,
)
from app.scoring.store import default_scoring_run_store
from app.signals.registry import default_signal_registry
from app.signals.schemas import ExtractionRunResponse
from app.signals.store import default_extraction_run_store
from app.storage import default_storage_factory

client = TestClient(app)


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_in_memory():
    """Ensure in-memory stores and presets are reset before each test."""
    default_storage_factory.configure(backend="memory")
    default_config_store.reset()
    default_scoring_config_store.reset()
    default_dataset_store.reset()
    default_extraction_run_store.reset()
    default_run_store.reset()
    default_scoring_run_store.reset()
    default_ranking_run_store.reset()
    yield
    default_storage_factory.configure(backend="memory")



@pytest.fixture(scope="module")
def postgres_test_engine():
    """Provide a validated test engine for PostgreSQL tests, skipping if unset."""
    test_url = os.getenv("TEST_DATABASE_URL")
    if not test_url or not test_url.strip():
        pytest.skip("TEST_DATABASE_URL is not configured.")
    assert_safe_test_database(test_url)

    from alembic import command
    from alembic.config import Config

    ini_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    alembic_cfg = Config(ini_path)
    alembic_cfg.attributes["override_url"] = test_url
    command.upgrade(alembic_cfg, "head")

    engine = create_app_engine(test_url)
    yield engine
    engine.dispose()


# ---------------------------------------------------------------------------
# 1. Reset Guard Tests (Section A)
# ---------------------------------------------------------------------------


class TestResetGuard:
    def test_reset_with_default_app_engine_raises_value_error(self, monkeypatch):
        """Postgres store reset() without a safe test engine rejects reset before executing SQL."""
        import unittest.mock

        # Ensure no real database URLs are set in environment
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("DATABASE_URL_POOLED", raising=False)
        monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
        monkeypatch.setenv("STORAGE_BACKEND", "postgres")

        # 1. Calling reset() with engine=None and no DATABASE_URL raises ValueError cleanly
        store = PostgresRuleConfigStore(engine=None)
        with pytest.raises(ValueError) as exc:
            store.reset()
        assert "Safety check failed" in str(exc.value) or "test database" in str(exc.value).lower()
        assert "@" not in str(exc.value)

        # 2. Calling reset() with an engine configured with an intentionally unsafe database URL
        unsafe_engine = sa.create_engine(
            "postgresql+psycopg://unsafe_user:secret_password@production.neon.tech:5432/main_db"
        )
        unsafe_store = PostgresRuleConfigStore(engine=unsafe_engine)

        # Instrument the session/execution boundary to confirm NO SQL statement is issued
        mock_session_scope = unittest.mock.MagicMock()
        monkeypatch.setattr(unsafe_store, "session", mock_session_scope)

        with pytest.raises(ValueError) as exc_unsafe:
            unsafe_store.reset()

        assert "Safety check failed" in str(exc_unsafe.value)
        # Verify credentials and sensitive connection parameters are never leaked
        assert "@" not in str(exc_unsafe.value)
        assert "secret_password" not in str(exc_unsafe.value)
        # Verify safety guard intercepted execution before any session or SQL was executed
        assert mock_session_scope.call_count == 0

    def test_reset_with_injected_test_engine_succeeds(self, postgres_test_engine):
        """Postgres store reset() with validated test engine executes DELETE without error."""
        from app.storage import reset_test_database

        reset_test_database(postgres_test_engine)
        store = PostgresRuleConfigStore(engine=postgres_test_engine)
        store.reset()




# ---------------------------------------------------------------------------
# 2. ID-Only Mode & Provenance Inheritance Tests (Section B)
# ---------------------------------------------------------------------------


class TestIdOnlyMode:
    @pytest.fixture
    def seeded_dataset_and_signals(self):
        """Seed a simple test dataset and extraction run in memory store."""
        csv_data = b"team_id,team_name,name,email,github_url,cgpa\nT1,Team One,Alice,alice@example.com,https://github.com/alice,8.5\nT1,Team One,Bob,bob@example.com,https://github.com/bob,8.0\n"
        parsed = parse_csv(csv_data)
        ds = DatasetRecord(
            dataset_id="ds_test_100",
            filename="teams.csv",
            file_type="csv",
            teams_count=parsed.teams_count,
            members_count=parsed.members_count,
            payload=parsed.model_dump(),
        )
        default_dataset_store.save(ds)

        raw_teams = [t.model_dump() for t in parsed.teams]
        ext_run = default_signal_registry.execute_extraction(
            teams=raw_teams,
            selected_signals=["academic_cgpa"],
        )
        ext_run.dataset_id = "ds_test_100"
        default_extraction_run_store.save(ext_run)

        return ds, ext_run

    def test_rules_evaluate_id_only_success(self, seeded_dataset_and_signals):
        ds, ext = seeded_dataset_and_signals
        resp = client.post(
            "/api/rules/evaluate",
            json={
                "dataset_id": ds.dataset_id,
                "extraction_run_id": ext.run_id,
                "config_id": "basic",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["dataset_id"] == ds.dataset_id
        assert body["extraction_run_id"] == ext.run_id
        assert len(body["teams"]) == 1
        assert body["teams"][0]["status"] == "ELIGIBLE"

    def test_rules_evaluate_unknown_dataset_404(self, seeded_dataset_and_signals):
        _, ext = seeded_dataset_and_signals
        resp = client.post(
            "/api/rules/evaluate",
            json={
                "dataset_id": "ds_unknown_999",
                "extraction_run_id": ext.run_id,
                "config_id": "basic",
            },
        )
        assert resp.status_code == 404
        assert "Dataset 'ds_unknown_999' not found" in resp.json()["detail"]

    def test_rules_evaluate_unknown_extraction_run_404(self, seeded_dataset_and_signals):
        ds, _ = seeded_dataset_and_signals
        resp = client.post(
            "/api/rules/evaluate",
            json={
                "dataset_id": ds.dataset_id,
                "extraction_run_id": "run_unknown_999",
                "config_id": "basic",
            },
        )
        assert resp.status_code == 404
        assert "Extraction run 'run_unknown_999' not found" in resp.json()["detail"]

    def test_rules_evaluate_mismatched_dataset_id_400(self, seeded_dataset_and_signals):
        _, ext = seeded_dataset_and_signals
        # Register second dataset
        ds2 = DatasetRecord(
            dataset_id="ds_other_200",
            filename="teams2.csv",
            file_type="csv",
            teams_count=0,
            members_count=0,
            payload={"teams": []},
        )
        default_dataset_store.save(ds2)

        resp = client.post(
            "/api/rules/evaluate",
            json={
                "dataset_id": "ds_other_200",
                "extraction_run_id": ext.run_id,
                "config_id": "basic",
            },
        )
        assert resp.status_code == 400
        assert "does not match supplied dataset_id" in resp.json()["detail"]

    def test_omitting_teams_without_dataset_id_gives_validation_error(self):
        resp = client.post(
            "/api/rules/evaluate",
            json={"config_id": "basic"},
        )
        assert resp.status_code in (400, 422)

    def test_scoring_evaluate_id_only_and_provenance_inheritance(self, seeded_dataset_and_signals):
        ds, ext = seeded_dataset_and_signals
        # 1. Run eligibility
        elig_resp = client.post(
            "/api/rules/evaluate",
            json={
                "dataset_id": ds.dataset_id,
                "extraction_run_id": ext.run_id,
                "config_id": "basic",
            },
        )
        elig_run_id = elig_resp.json()["run_id"]

        # 2. Run scoring omitting dataset_id and extraction_run_id -> inherits from elig_run
        score_resp = client.post(
            "/api/scoring/evaluate",
            json={
                "eligibility_run_id": elig_run_id,
                "config_id": "balanced",
            },
        )
        assert score_resp.status_code == 200
        score_body = score_resp.json()
        assert score_body["dataset_id"] == ds.dataset_id
        assert score_body["extraction_run_id"] == ext.run_id
        assert score_body["eligibility_run_id"] == elig_run_id

    def test_scoring_explicit_provenance_not_overwritten(self, seeded_dataset_and_signals):
        ds, ext = seeded_dataset_and_signals
        elig_resp = client.post(
            "/api/rules/evaluate",
            json={
                "dataset_id": ds.dataset_id,
                "extraction_run_id": ext.run_id,
                "config_id": "basic",
            },
        )
        elig_run_id = elig_resp.json()["run_id"]

        # Provide explicit extraction_run_id
        score_resp = client.post(
            "/api/scoring/evaluate",
            json={
                "dataset_id": ds.dataset_id,
                "extraction_run_id": ext.run_id,
                "eligibility_run_id": elig_run_id,
                "config_id": "balanced",
            },
        )
        assert score_resp.status_code == 200
        assert score_resp.json()["dataset_id"] == ds.dataset_id
        assert score_resp.json()["extraction_run_id"] == ext.run_id

    def test_ranking_evaluate_option_c_id_only(self, seeded_dataset_and_signals):
        ds, ext = seeded_dataset_and_signals
        resp = client.post(
            "/api/ranking/evaluate",
            json={
                "dataset_id": ds.dataset_id,
                "extraction_run_id": ext.run_id,
                "top_x": 3,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["dataset_id"] == ds.dataset_id
        assert body["extraction_run_id"] == ext.run_id
        assert len(body["selected_teams"]) == 1

    def test_payload_mode_remains_unchanged(self):
        """Sending teams and signals directly continues to work without requiring dataset_id."""
        teams = [{
            "team_id": "T_INLINE",
            "team_name": "Inline Team",
            "members": [
                {
                    "member_id": "M1",
                    "name": "Dan",
                    "github_url": "https://github.com/dan",
                    "custom_fields": {},
                    "raw_data": {},
                },
                {
                    "member_id": "M2",
                    "name": "Eve",
                    "github_url": "https://github.com/eve",
                    "custom_fields": {},
                    "raw_data": {},
                },
            ],
        }]
        resp = client.post(
            "/api/rules/evaluate",
            json={"teams": teams, "config_id": "basic"},
        )
        assert resp.status_code == 200
        assert resp.json()["summary"]["eligible_count"] == 1


# ---------------------------------------------------------------------------
# 3. Explicit Empty Lists Handling (Prompt 5.1 Section 3)
# ---------------------------------------------------------------------------


class TestEmptyListHandling:
    """Verifies that explicitly passing teams: [] does not trigger silent fallback to dataset_id."""

    @pytest.fixture
    def populated_dataset(self):
        ds = DatasetRecord(
            dataset_id="ds_empty_test_check",
            filename="test.csv",
            file_type="csv",
            teams_count=1,
            members_count=2,
            payload={
                "teams": [
                    {
                        "team_id": "T_SHOULD_NOT_BE_LOADED",
                        "team_name": "Ghost Team",
                        "members": [
                            {"member_id": "M1", "name": "A", "github_url": "https://github.com/a"},
                            {"member_id": "M2", "name": "B", "github_url": "https://github.com/b"},
                        ],
                    }
                ]
            },
        )
        default_dataset_store.save(ds)
        return ds

    def test_rules_evaluate_explicit_empty_teams_does_not_load_dataset(self, populated_dataset):
        resp = client.post(
            "/api/rules/evaluate",
            json={
                "teams": [],
                "dataset_id": populated_dataset.dataset_id,
                "config_id": "basic",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["teams"]) == 0
        assert data["summary"]["total_teams"] == 0

    def test_scoring_evaluate_explicit_empty_teams_does_not_load_dataset(self, populated_dataset):
        resp = client.post(
            "/api/scoring/evaluate",
            json={
                "teams": [],
                "dataset_id": populated_dataset.dataset_id,
                "config_id": "balanced",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["teams"]) == 0
        assert data["summary"]["total_teams"] == 0

    def test_ranking_evaluate_explicit_empty_teams_does_not_load_dataset(self, populated_dataset):
        resp = client.post(
            "/api/ranking/evaluate",
            json={
                "teams": [],
                "dataset_id": populated_dataset.dataset_id,
                "top_x": 5,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["selected_teams"]) == 0
        assert len(data["ranked_teams"]) == 0

    def test_signals_extract_explicit_empty_teams_does_not_load_dataset(self, populated_dataset):
        resp = client.post(
            "/api/signals/extract",
            json={
                "teams": [],
                "dataset_id": populated_dataset.dataset_id,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["teams"]) == 0
        assert data["total_teams"] == 0

    def test_omitted_teams_loads_from_dataset(self, populated_dataset):
        """When teams is omitted or null, dataset_id is used."""
        resp = client.post(
            "/api/rules/evaluate",
            json={
                "dataset_id": populated_dataset.dataset_id,
                "config_id": "basic",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["teams"]) == 1
        assert data["teams"][0]["team_id"] == "T_SHOULD_NOT_BE_LOADED"

    def test_omitted_both_teams_and_dataset_id_rejected(self):
        """When both teams and dataset_id are omitted, request is rejected."""
        resp = client.post(
            "/api/rules/evaluate",
            json={"config_id": "basic"},
        )
        assert resp.status_code in (400, 422)


# ---------------------------------------------------------------------------
# 4. CSV Export Tests (Prompt 5.1 Section 4)
# ---------------------------------------------------------------------------


class TestCsvExport:
    @pytest.fixture
    def seeded_ranking_run(self):
        """Seed a representative ranking run with all 5 selection statuses and formula injection characters."""
        run = RankingRunResponse(
            run_id="rank_run_test_csv",
            evaluated_at="2026-10-17T12:00:00Z",
            top_x=1,
            selected_teams=[
                RankedTeamResult(
                    rank=1,
                    team_id="T_SEL",
                    team_name="=Formula Team",  # Formula injection candidate: '='
                    final_score=95.0,
                    eligibility_status=EligibilityStatus.ELIGIBLE,
                    score_status=ScoreStatus.CALCULATED,
                    is_tied=False,
                    selection_status=SelectionStatus.SELECTED,
                    criteria_breakdown_summary={"c1": "1 of 4"},
                    explanation="Selected #1",
                )
            ],
            ranked_teams=[
                RankedTeamResult(
                    rank=1,
                    team_id="T_SEL",
                    team_name="=Formula Team",
                    final_score=95.0,
                    eligibility_status=EligibilityStatus.ELIGIBLE,
                    score_status=ScoreStatus.CALCULATED,
                    is_tied=False,
                    selection_status=SelectionStatus.SELECTED,
                ),
                RankedTeamResult(
                    rank=2,
                    team_id="T_OTHER",
                    team_name="+Plus Team",  # Formula injection candidate: '+'
                    final_score=85.0,
                    eligibility_status=EligibilityStatus.ELIGIBLE,
                    score_status=ScoreStatus.CALCULATED,
                    is_tied=False,
                    selection_status=SelectionStatus.NOT_SELECTED,
                    explanation="Ranked #2",
                ),
            ],
            needs_review_teams=[
                RankedTeamResult(
                    rank=3,
                    team_id="T_REVIEW",
                    team_name="@At Team",  # Formula injection candidate: '@'
                    final_score=75.0,
                    eligibility_status=EligibilityStatus.NEEDS_REVIEW,
                    score_status=ScoreStatus.CALCULATED,
                    is_tied=False,
                    selection_status=SelectionStatus.NEEDS_REVIEW,
                    explanation="Needs manual review",
                )
            ],
            unresolved_teams=[
                ExcludedTeamResult(
                    team_id="T_UNRES",
                    team_name="-Minus Team",  # Formula injection candidate: '-'
                    final_score=60.0,
                    eligibility_status=EligibilityStatus.ELIGIBLE,
                    score_status=ScoreStatus.CALCULATED,
                    reason_code=ExclusionReason.UNRESOLVED,
                    explanation="Duplicate team name unresolved",
                )
            ],
            excluded_teams=[
                ExcludedTeamResult(
                    team_id="T_EXCL",
                    team_name="Excluded Team",
                    final_score=50.0,
                    eligibility_status=EligibilityStatus.INELIGIBLE,
                    score_status=ScoreStatus.CALCULATED,
                    reason_code=ExclusionReason.INELIGIBLE,
                    explanation="Failed hard sizing criteria",
                )
            ],
        )
        default_ranking_run_store.save(run)
        return run

    def test_csv_export_headers_and_utf8_bom(self, seeded_ranking_run):
        resp = client.get(f"/api/ranking/runs/{seeded_ranking_run.run_id}/export")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        assert f'filename="ranking_run_{seeded_ranking_run.run_id}.csv"' in resp.headers["content-disposition"]
        # UTF-8 with BOM prefix
        assert resp.content.startswith(b"\xef\xbb\xbf")

    def test_csv_export_404_for_unknown_run(self):
        resp = client.get("/api/ranking/runs/unknown_run_xyz/export")
        assert resp.status_code == 404

    def test_csv_formula_injection_mitigation(self, seeded_ranking_run):
        resp = client.get(f"/api/ranking/runs/{seeded_ranking_run.run_id}/export")
        text = resp.content.decode("utf-8-sig")
        # Ensure '=', '+', '-', '@' are sanitized with leading single quote
        assert "'=Formula Team" in text
        assert "'+Plus Team" in text
        assert "'@At Team" in text
        assert "'-Minus Team" in text

    def test_csv_row_order_and_columns(self, seeded_ranking_run):
        resp = client.get(f"/api/ranking/runs/{seeded_ranking_run.run_id}/export")
        text = resp.content.decode("utf-8-sig")
        lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
        header = lines[0]
        expected_cols = [
            "selection_status",
            "rank",
            "team_id",
            "team_name",
            "final_score",
            "eligibility_status",
            "score_status",
            "is_tied",
            "criteria_evaluated",
            "reason_code",
            "explanation",
        ]
        assert header == ",".join(expected_cols)

        # Verify all 5 categories appear in exact required sequence:
        # 1. SELECTED -> 2. NOT_SELECTED (other ranked) -> 3. NEEDS_REVIEW -> 4. UNRESOLVED -> 5. EXCLUDED
        data_lines = lines[1:]
        statuses = [l.split(",")[0] for l in data_lines]
        assert statuses == ["SELECTED", "NOT_SELECTED", "NEEDS_REVIEW", "UNRESOLVED", "EXCLUDED"]

    def test_csv_export_immutability(self, seeded_ranking_run):
        """Exporting a stored ranking run does not re-evaluate or modify the stored run."""
        from unittest.mock import patch

        with patch("app.api.endpoints.ranking.evaluate_ranking") as mock_eval:
            resp = client.get(f"/api/ranking/runs/{seeded_ranking_run.run_id}/export")
            assert resp.status_code == 200
            mock_eval.assert_not_called()

        persisted = default_ranking_run_store.get(seeded_ranking_run.run_id)
        assert persisted.evaluated_at == seeded_ranking_run.evaluated_at
        assert len(persisted.selected_teams) == len(seeded_ranking_run.selected_teams)


# ---------------------------------------------------------------------------
# 4. Sample CSV Pipeline Test (Section D)
# ---------------------------------------------------------------------------


class TestSampleDataPipeline:
    def test_demo_teams_csv_produces_documented_outcomes(self):
        """Verify that demo_teams.csv produces the outcomes documented in sample_data/README.md."""
        csv_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "sample_data",
            "demo_teams.csv",
        )
        assert os.path.exists(csv_path), "demo_teams.csv must exist"
        with open(csv_path, "rb") as f:
            content = f.read()

        parsed = parse_csv(content)
        assert parsed.teams_count == 15
        assert parsed.members_count == 29

        ds = DatasetRecord(
            dataset_id="ds_demo_test",
            filename="demo_teams.csv",
            file_type="csv",
            teams_count=parsed.teams_count,
            members_count=parsed.members_count,
            payload=parsed.model_dump(),
        )
        default_dataset_store.save(ds)

        raw_teams = [t.model_dump() for t in parsed.teams]
        ext_run = default_signal_registry.execute_extraction(
            teams=raw_teams,
            selected_signals=["academic_cgpa", "academic_year"],
        )
        ext_run.dataset_id = "ds_demo_test"
        default_extraction_run_store.save(ext_run)

        # 1. Eligibility Basic
        elig_resp = client.post(
            "/api/rules/evaluate",
            json={
                "dataset_id": "ds_demo_test",
                "extraction_run_id": ext_run.run_id,
                "config_id": "basic",
            },
        )
        assert elig_resp.status_code == 200
        elig_data = elig_resp.json()
        assert elig_data["summary"]["eligible_count"] == 13
        assert elig_data["summary"]["ineligible_count"] == 2  # T06 (size) and T07 (no github)

        # 2. Scoring Balanced
        score_resp = client.post(
            "/api/scoring/evaluate",
            json={
                "dataset_id": "ds_demo_test",
                "extraction_run_id": ext_run.run_id,
                "eligibility_run_id": elig_data["run_id"],
                "config_id": "balanced",
            },
        )
        assert score_resp.status_code == 200
        score_data = score_resp.json()
        assert score_data["summary"]["calculated_teams"] == 14
        assert score_data["summary"]["no_score_teams"] == 1  # T08

        # 3. Ranking Top-5
        rank_resp = client.post(
            "/api/ranking/evaluate",
            json={
                "scoring_run_id": score_data["run_id"],
                "top_x": 5,
            },
        )
        assert rank_resp.status_code == 200
        rank_data = rank_resp.json()
        assert len(rank_data["selected_teams"]) == 5
        selected_ids = [t["team_id"] for t in rank_data["selected_teams"]]
        assert selected_ids == ["T01", "T12", "T02", "T10", "T11"]

        # Verify unresolved teams
        assert len(rank_data["unresolved_teams"]) == 2
        # Verify score tie between T02 and T10 (both 57.50)
        t02 = next(t for t in rank_data["selected_teams"] if t["team_id"] == "T02")
        t10 = next(t for t in rank_data["selected_teams"] if t["team_id"] == "T10")
        assert t02["final_score"] == 57.50
        assert t10["final_score"] == 57.50
        assert t02["is_tied"] is True
        assert t10["is_tied"] is True


# ---------------------------------------------------------------------------
# 5. Mixed Eligibility Demo Scenario & Reviewer Override (Prompt 5.1 Section 2)
# ---------------------------------------------------------------------------


class TestMixedEligibilityDemoScenario:
    """Verifies a reproducible mixed eligibility scenario (ELIGIBLE + NEEDS_REVIEW) and reviewer override."""

    def test_mixed_eligibility_and_reviewer_override_workflow(self):
        # 1. Parse demo_teams.csv
        csv_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "sample_data",
            "demo_teams.csv",
        )
        assert os.path.exists(csv_path)
        with open(csv_path, "rb") as f:
            content = f.read()

        parsed = parse_csv(content)
        ds = DatasetRecord(
            dataset_id="ds_mixed_demo",
            filename="demo_teams.csv",
            file_type="csv",
            teams_count=parsed.teams_count,
            members_count=parsed.members_count,
            payload=parsed.model_dump(),
        )
        default_dataset_store.save(ds)

        raw_teams = [t.model_dump() for t in parsed.teams]
        ext_run = default_signal_registry.execute_extraction(
            teams=raw_teams,
            selected_signals=["academic_cgpa", "academic_year"],
        )
        ext_run.dataset_id = "ds_mixed_demo"
        default_extraction_run_store.save(ext_run)

        # 2. Verify built-in preset 'demo_mixed_review' is available without manual POST
        cfg_resp = client.get("/api/rules/configs/demo_mixed_review")
        assert cfg_resp.status_code == 200
        preset_cfg = cfg_resp.json()
        assert preset_cfg["config_id"] == "demo_mixed_review"
        assert preset_cfg["name"] == "Demo: Lead Academic Review"
        assert len(preset_cfg["rules"]) == 3


        # 3. Evaluate eligibility
        elig_resp = client.post(
            "/api/rules/evaluate",
            json={
                "dataset_id": "ds_mixed_demo",
                "extraction_run_id": ext_run.run_id,
                "config_id": "demo_mixed_review",
            },
        )
        assert elig_resp.status_code == 200
        elig_data = elig_resp.json()
        summary = elig_data["summary"]
        assert summary["eligible_count"] == 10
        assert summary["needs_review_count"] == 1
        assert summary["ineligible_count"] == 4

        # Team T02 requires review because it lacks a designated lead
        t02_elig = next(t for t in elig_data["teams"] if t["team_id"] == "T02")
        assert t02_elig["status"] == "NEEDS_REVIEW"

        # 4. Evaluate scoring (balanced preset)
        score_resp = client.post(
            "/api/scoring/evaluate",
            json={
                "dataset_id": "ds_mixed_demo",
                "extraction_run_id": ext_run.run_id,
                "eligibility_run_id": elig_data["run_id"],
                "config_id": "balanced",
            },
        )
        assert score_resp.status_code == 200
        score_data = score_resp.json()

        # 5. Evaluate ranking before override (top_x = 5)
        rank_resp_1 = client.post(
            "/api/ranking/evaluate",
            json={
                "scoring_run_id": score_data["run_id"],
                "top_x": 5,
                "eligibility_run_id": elig_data["run_id"],
            },
        )
        assert rank_resp_1.status_code == 200
        rank_1 = rank_resp_1.json()

        # T02 is in needs_review_teams, not selected_teams
        assert any(t["team_id"] == "T02" for t in rank_1["needs_review_teams"])
        selected_ids_1 = [t["team_id"] for t in rank_1["selected_teams"]]
        assert selected_ids_1 == ["T01", "T12", "T10", "T11", "T05"]

        # 6. Reviewer applies manual eligibility override to T02 -> ELIGIBLE
        ovr_resp = client.post(
            f"/api/rules/runs/{elig_data['run_id']}/teams/T02/override",
            json={
                "override_status": "ELIGIBLE",
                "reason": "Team lead Charlie Brown verified manually; CGPA 8.4 meets threshold.",
                "overridden_by": "reviewer",
            },
        )
        assert ovr_resp.status_code == 200

        # 7. Evaluate ranking after override
        rank_resp_2 = client.post(
            "/api/ranking/evaluate",
            json={
                "scoring_run_id": score_data["run_id"],
                "top_x": 5,
                "eligibility_run_id": elig_data["run_id"],
            },
        )
        assert rank_resp_2.status_code == 200
        rank_2 = rank_resp_2.json()

        # T02 is now in selected_teams at Rank #3, pushing T05 down to Rank #6 (NOT_SELECTED)
        selected_ids_2 = [t["team_id"] for t in rank_2["selected_teams"]]
        assert selected_ids_2 == ["T01", "T12", "T02", "T10", "T11"]
        assert len(rank_2["needs_review_teams"]) == 0
        t05_ranked = next(t for t in rank_2["ranked_teams"] if t["team_id"] == "T05")
        assert t05_ranked["selection_status"] == "NOT_SELECTED"
        assert t05_ranked["rank"] == 6


# ---------------------------------------------------------------------------
# 6. Full PostgreSQL ID-Only Integration Test (Skipped when unset)
# ---------------------------------------------------------------------------


class TestPostgresIdOnlyPipeline:
    def test_full_id_only_pipeline_postgres(self, postgres_test_engine):
        """Execute full dataset -> extraction -> rules -> scoring -> ranking on PostgreSQL."""
        from app.db.seeding import seed_database_presets
        from app.storage import reset_test_database

        try:
            default_storage_factory.configure(backend="postgres", engine=postgres_test_engine)
            seed_database_presets(engine=postgres_test_engine)

            csv_data = b"team_id,team_name,name,email,github_url,cgpa\nTPG1,PG Team,Ada,ada@example.com,https://github.com/ada,9.0\nTPG1,PG Team,Grace,grace@example.com,https://github.com/grace,9.5\n"
            parsed = parse_csv(csv_data)
            ds = DatasetRecord(
                dataset_id="ds_pg_001",
                filename="pg_teams.csv",
                file_type="csv",
                teams_count=parsed.teams_count,
                members_count=parsed.members_count,
                payload=parsed.model_dump(),
            )
            default_dataset_store.save(ds)

            raw_teams = [t.model_dump() for t in parsed.teams]
            ext_run = default_signal_registry.execute_extraction(
                teams=raw_teams,
                selected_signals=["academic_cgpa"],
            )
            ext_run.dataset_id = "ds_pg_001"
            default_extraction_run_store.save(ext_run)

            # 1. Rules evaluate (ID-only)
            resp = client.post(
                "/api/rules/evaluate",
                json={
                    "dataset_id": "ds_pg_001",
                    "extraction_run_id": ext_run.run_id,
                    "config_id": "basic",
                },
            )
            assert resp.status_code == 200
            elig_data = resp.json()
            assert elig_data["dataset_id"] == "ds_pg_001"
            assert elig_data["teams"][0]["status"] == "ELIGIBLE"

            # 2. Scoring evaluate (ID-only + provenance inheritance)
            score_resp = client.post(
                "/api/scoring/evaluate",
                json={
                    "eligibility_run_id": elig_data["run_id"],
                    "config_id": "balanced",
                },
            )
            assert score_resp.status_code == 200
            score_data = score_resp.json()
            assert score_data["dataset_id"] == "ds_pg_001"

            # 3. Ranking evaluate (ID-only + provenance inheritance)
            rank_resp = client.post(
                "/api/ranking/evaluate",
                json={
                    "scoring_run_id": score_data["run_id"],
                    "top_x": 1,
                },
            )
            assert rank_resp.status_code == 200
            rank_data = rank_resp.json()
            assert len(rank_data["selected_teams"]) == 1
            assert rank_data["dataset_id"] == "ds_pg_001"
        finally:
            reset_test_database(postgres_test_engine)
            default_storage_factory.configure(backend="memory")

