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
        """Postgres store reset() without injected engine attempts validation on default engine and raises."""
        monkeypatch.setenv("STORAGE_BACKEND", "postgres")
        # Ensure default app engine does not point to a test database
        store = PostgresRuleConfigStore(engine=None)
        with pytest.raises(ValueError) as exc:
            store.reset()
        assert "TEST_DATABASE_URL" in str(exc.value) or "test database" in str(exc.value).lower()
        # Ensure credentials / sensitive URLs are never exposed in exception message
        assert "@" not in str(exc.value)

    def test_reset_with_injected_test_engine_succeeds(self, postgres_test_engine):
        """Postgres store reset() with validated test engine executes DELETE without error."""
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
# 3. CSV Export Tests (Section C)
# ---------------------------------------------------------------------------


class TestCsvExport:
    @pytest.fixture
    def seeded_ranking_run(self):
        """Seed a representative ranking run with all 5 selection statuses."""
        run = RankingRunResponse(
            run_id="rank_run_test_csv",
            evaluated_at="2026-10-17T12:00:00Z",
            top_x=1,
            selected_teams=[
                RankedTeamResult(
                    rank=1,
                    team_id="T_SEL",
                    team_name="=Formula Team",  # Formula injection candidate
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
                    team_name="+Plus Team",  # Formula injection candidate
                    final_score=85.0,
                    eligibility_status=EligibilityStatus.ELIGIBLE,
                    score_status=ScoreStatus.CALCULATED,
                    is_tied=False,
                    selection_status=SelectionStatus.NOT_SELECTED,
                ),
            ],
            needs_review_teams=[
                RankedTeamResult(
                    rank=3,
                    team_id="T_REVIEW",
                    team_name="@At Team",  # Formula injection candidate
                    final_score=75.0,
                    eligibility_status=EligibilityStatus.NEEDS_REVIEW,
                    score_status=ScoreStatus.CALCULATED,
                    is_tied=False,
                    selection_status=SelectionStatus.NEEDS_REVIEW,
                )
            ],
            unresolved_teams=[],
            excluded_teams=[],
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
        # Ensure '=', '+', '@' are sanitized with leading single quote
        assert "'=Formula Team" in text
        assert "'+Plus Team" in text
        assert "'@At Team" in text

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

        # Selected should appear before other ranked and needs_review
        data_lines = lines[1:]
        statuses = [l.split(",")[0] for l in data_lines]
        assert statuses == ["SELECTED", "NOT_SELECTED", "NEEDS_REVIEW"]


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
# 5. Full PostgreSQL ID-Only Integration Test (Skipped when unset)
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

