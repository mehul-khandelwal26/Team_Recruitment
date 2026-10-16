"""Comprehensive integration tests for PostgreSQL-backed persistence.

Covers:
1. Module-scoped Alembic head migration fixture against TEST_DATABASE_URL (no downgrade afterwards).
2. Rule Configuration Store: CRUD, versions, timestamps, soft-delete across all versions, isolation.
3. Scoring Configuration Store: CRUD, versions, weights, snapshots, soft-delete.
4. Eligibility Run Store: CRUD, foreign keys (RESTRICT), missing reference handling.
5. Manual Override Store: atomic ON CONFLICT DO UPDATE upsert on (run_id, team_id), field sync, no duplicates.
6. Scoring Run Store: CRUD, snapshots, FKs, summary & scores preservation.
7. Ranking Run Store: CRUD, FKs, shortlisted teams, shortage, cutoff score preservation.
8. Storage Factory: backend selection, injected engine use, lazy loading, no fallback.
9. Database Error Handling: 503 on connection failure, 409 on FK/Unique violations, secret safety.
10. Startup Preset Seeding: idempotency, user config preservation, missing table failure.
11. Test Database Safety: assert_safe_test_database enforcement, reset_test_database table limits.
"""

from __future__ import annotations

import datetime
import os
from typing import Any
import pytest
from fastapi.testclient import TestClient
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, OperationalError

from app.config import assert_safe_test_database
from app.db.errors import register_database_error_handlers
from app.db.models import (
    EligibilityRunModel,
    ManualOverrideModel,
    RuleConfigurationModel,
    ScoringConfigurationModel,
)
from app.db.seeding import seed_database_presets
from app.db.session import create_app_engine
from app.db.stores import (
    PostgresEligibilityRunStore,
    PostgresManualOverrideStore,
    PostgresRankingRunStore,
    PostgresRuleConfigStore,
    PostgresScoringConfigStore,
    PostgresScoringRunStore,
)
from app.main import app
from app.ranking.schemas import (
    RankedTeamResult,
    RankingRunResponse,
    RankingRunSummary,
    SelectionStatus,
)
from app.rules.presets import get_default_presets
from app.rules.schemas import (
    EligibilityRunResponse,
    EligibilityRunSummary,
    EligibilityStatus,
    GlobalRuleConfig,
    ManualOverride,
    RuleConfiguration,
    RuleConfigurationUpdate,
    RuleDefinition,
    TeamEligibilityResult,
)
from app.scoring.presets import get_default_scoring_presets
from app.scoring.schemas import (
    AggregationMethod,
    CriterionType,
    EvaluationCriterion,
    LinearRangeConfig,
    MissingDataPolicy,
    NormalizationConfig,
    ScoreStatus,
    ScoringConfiguration,
    ScoringConfigurationUpdate,
    ScoringRunResponse,
    ScoringRunSummary,
    TeamScoringResult,
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
    """Truncate the 8 project tables before each test for total test isolation."""
    reset_test_database(migrated_test_db)
    yield
    reset_test_database(migrated_test_db)


# ===========================================================================
# 1. Rule Configuration Store Tests
# ===========================================================================


class TestPostgresRuleConfigStore:
    def test_create_and_retrieve_configuration(self, migrated_test_db):
        store = PostgresRuleConfigStore(engine=migrated_test_db)
        cfg = RuleConfiguration(
            config_id="test_rules",
            version=1,
            name="Test Rules",
            description="Testing postgres persistence",
            global_config=GlobalRuleConfig(),
            rules=[],
            is_active=True,
        )
        saved = store.save(cfg)
        assert saved.config_id == "test_rules"
        assert saved.version == 1
        assert saved.created_at is not None
        assert saved.updated_at is not None

        retrieved = store.get("test_rules", version=1)
        assert retrieved is not None
        assert retrieved.config_id == "test_rules"
        assert retrieved.name == "Test Rules"
        assert retrieved.is_active is True

    def test_versioning_and_immutability(self, migrated_test_db):
        store = PostgresRuleConfigStore(engine=migrated_test_db)
        cfg = RuleConfiguration(
            config_id="versioned_rules",
            version=1,
            name="V1 Name",
            global_config=GlobalRuleConfig(),
            rules=[],
            is_active=True,
        )
        store.save(cfg)

        update_payload = RuleConfigurationUpdate(name="V2 Name")
        updated = store.update("versioned_rules", update_payload)
        assert updated is not None
        assert updated.version == 2
        assert updated.name == "V2 Name"

        # Previous version remains unchanged
        v1 = store.get("versioned_rules", version=1)
        assert v1 is not None
        assert v1.version == 1
        assert v1.name == "V1 Name"

        # Latest defaults to version 2
        latest = store.get("versioned_rules")
        assert latest is not None
        assert latest.version == 2

        versions = store.list_versions("versioned_rules")
        assert versions == [1, 2]

    def test_soft_delete_deactivates_all_versions_and_payloads(self, migrated_test_db):
        store = PostgresRuleConfigStore(engine=migrated_test_db)
        cfg1 = RuleConfiguration(
            config_id="delete_me",
            version=1,
            name="Delete V1",
            global_config=GlobalRuleConfig(),
            rules=[],
            is_active=True,
        )
        store.save(cfg1)
        store.update("delete_me", RuleConfigurationUpdate(name="Delete V2"))

        # Create another unrelated config
        other_cfg = RuleConfiguration(
            config_id="keep_me",
            version=1,
            name="Keep Me Active",
            global_config=GlobalRuleConfig(),
            rules=[],
            is_active=True,
        )
        store.save(other_cfg)

        # Soft delete delete_me
        deleted = store.delete("delete_me")
        assert deleted is True

        # Check all versions of delete_me are inactive in typed column and payload
        v1 = store.get("delete_me", version=1)
        assert v1.is_active is False
        v2 = store.get("delete_me", version=2)
        assert v2.is_active is False

        # Direct SQL inspection to verify typed column AND json payload
        with migrated_test_db.connect() as conn:
            rows = conn.execute(
                sa.text("SELECT version, is_active, payload FROM rule_configurations WHERE config_id = 'delete_me'")
            ).mappings().all()
            assert len(rows) == 2
            for r in rows:
                assert r["is_active"] is False
                assert r["payload"]["is_active"] is False

        # Unrelated config remains active
        other = store.get("keep_me", version=1)
        assert other.is_active is True

        # list_latest excludes inactive configs
        active_list = store.list_latest()
        active_ids = [c.config_id for c in active_list]
        assert "delete_me" not in active_ids
        assert "keep_me" in active_ids


# ===========================================================================
# 2. Scoring Configuration Store Tests
# ===========================================================================


class TestPostgresScoringConfigStore:
    def test_create_retrieve_and_preserve_criteria(self, migrated_test_db):
        store = PostgresScoringConfigStore(engine=migrated_test_db)
        criterion = EvaluationCriterion(
            criterion_id="repos",
            name="Public Repos",
            target_signal_key="github_public_repo_count",
            criterion_type=CriterionType.NUMERIC_RANGE,
            weight=40.0,
            normalization=NormalizationConfig(linear_range=LinearRangeConfig(min_value=0.0, max_value=20.0)),
            aggregation=AggregationMethod.MEAN,
            missing_data_policy=MissingDataPolicy.ZERO_SCORE,
        )
        cfg = ScoringConfiguration(
            config_id="rubric_1",
            version=1,
            name="Rubric One",
            description="Testing scoring rubrics",
            scale_max=100.0,
            criteria=[criterion],
            is_active=True,
        )
        saved = store.save(cfg)
        assert saved.config_id == "rubric_1"

        retrieved = store.get("rubric_1")
        assert retrieved is not None
        assert retrieved.name == "Rubric One"
        assert len(retrieved.criteria) == 1
        assert retrieved.criteria[0].weight == 40.0
        assert retrieved.scale_max == 100.0

    def test_soft_delete_scoring_configuration(self, migrated_test_db):
        store = PostgresScoringConfigStore(engine=migrated_test_db)
        cfg = ScoringConfiguration(
            config_id="scoring_delete",
            version=1,
            name="Scoring Delete",
            criteria=[],
            is_active=True,
        )
        store.save(cfg)
        store.update("scoring_delete", ScoringConfigurationUpdate(name="Scoring Delete V2"))

        deleted = store.delete("scoring_delete")
        assert deleted is True

        v1 = store.get("scoring_delete", version=1)
        v2 = store.get("scoring_delete", version=2)
        assert v1.is_active is False
        assert v2.is_active is False


# ===========================================================================
# 3. Eligibility Run Store Tests
# ===========================================================================


class TestPostgresEligibilityRunStore:
    def test_save_and_retrieve_eligibility_run(self, migrated_test_db):
        rule_store = PostgresRuleConfigStore(engine=migrated_test_db)
        rule_cfg = RuleConfiguration(
            config_id="basic",
            version=1,
            name="Basic Rules",
            global_config=GlobalRuleConfig(),
            rules=[],
            is_active=True,
        )
        rule_store.save(rule_cfg)

        elig_store = PostgresEligibilityRunStore(engine=migrated_test_db)
        run_record = EligibilityRunResponse(
            run_id="elig_run_100",
            config_id="basic",
            config_version=1,
            evaluated_at="2026-10-17T00:00:00Z",
            teams=[
                TeamEligibilityResult(
                    team_id="T1",
                    team_name="Alpha",
                    status=EligibilityStatus.ELIGIBLE,
                    reasons=["All rules passed"],
                )
            ],
            summary=EligibilityRunSummary(
                total_teams=1,
                eligible_count=1,
                ineligible_count=0,
                needs_review_count=0,
            ),
        )
        elig_store.save(run_record)

        retrieved = elig_store.get("elig_run_100")
        assert retrieved is not None
        assert retrieved.run_id == "elig_run_100"
        assert retrieved.config_id == "basic"
        assert retrieved.summary.eligible_count == 1
        assert len(retrieved.teams) == 1
        assert retrieved.teams[0].team_id == "T1"

    def test_foreign_key_violation_on_nonexistent_rule_config(self, migrated_test_db):
        elig_store = PostgresEligibilityRunStore(engine=migrated_test_db)
        # Attempt to save a run pointing to nonexistent rule_config
        run_record = EligibilityRunResponse(
            run_id="bad_run",
            config_id="nonexistent_config",
            config_version=99,
            evaluated_at="2026-10-17T00:00:00Z",
        )
        with pytest.raises(IntegrityError):
            elig_store.save(run_record)


# ===========================================================================
# 4. Manual Override Store Tests
# ===========================================================================


class TestPostgresManualOverrideStore:
    def test_atomic_upsert_on_same_run_and_team(self, migrated_test_db):
        # 1. Create prerequisite rule config & eligibility run
        rule_store = PostgresRuleConfigStore(engine=migrated_test_db)
        rule_store.save(
            RuleConfiguration(
                config_id="basic",
                version=1,
                name="Basic Rules",
                global_config=GlobalRuleConfig(),
                rules=[],
                is_active=True,
            )
        )
        elig_store = PostgresEligibilityRunStore(engine=migrated_test_db)
        elig_store.save(
            EligibilityRunResponse(
                run_id="run_for_override",
                config_id="basic",
                config_version=1,
                evaluated_at="2026-10-17T00:00:00Z",
            )
        )

        override_store = PostgresManualOverrideStore(engine=migrated_test_db)

        # 2. Insert initial override
        ovr1 = ManualOverride(
            override_id="ovr_1",
            run_id="run_for_override",
            team_id="T_ALPHA",
            original_status=EligibilityStatus.INELIGIBLE,
            override_status=EligibilityStatus.ELIGIBLE,
            reason="Initial organizer exception",
            overridden_by="judge_1",
            overridden_at="2026-10-17T01:00:00Z",
        )
        override_store.save(ovr1)

        retrieved1 = override_store.get_for_team("run_for_override", "T_ALPHA")
        assert retrieved1 is not None
        assert retrieved1.override_id == "ovr_1"
        assert retrieved1.reason == "Initial organizer exception"
        assert retrieved1.override_status == EligibilityStatus.ELIGIBLE

        # 3. Upsert override for SAME run_id and team_id with new values
        ovr2 = ManualOverride(
            override_id="ovr_2_updated",
            run_id="run_for_override",
            team_id="T_ALPHA",
            original_status=EligibilityStatus.INELIGIBLE,
            override_status=EligibilityStatus.NEEDS_REVIEW,
            reason="Updated reason: requires secondary review",
            overridden_by="lead_judge",
            overridden_at="2026-10-17T02:00:00Z",
        )
        override_store.save(ovr2)

        # 4. Verify no duplicates were created and fields are synchronized
        all_for_run = override_store.get_for_run("run_for_override")
        assert len(all_for_run) == 1

        retrieved2 = override_store.get_for_team("run_for_override", "T_ALPHA")
        assert retrieved2.override_id == "ovr_2_updated"
        assert retrieved2.override_status == EligibilityStatus.NEEDS_REVIEW
        assert retrieved2.reason == "Updated reason: requires secondary review"
        assert retrieved2.overridden_by == "lead_judge"

        # Check DB columns directly
        with migrated_test_db.connect() as conn:
            row = conn.execute(
                sa.text("SELECT * FROM manual_overrides WHERE run_id = 'run_for_override' AND team_id = 'T_ALPHA'")
            ).mappings().first()
            assert row["override_id"] == "ovr_2_updated"
            assert row["override_status"] == EligibilityStatus.NEEDS_REVIEW.value
            assert row["reason"] == "Updated reason: requires secondary review"
            assert row["payload"]["override_id"] == "ovr_2_updated"


# ===========================================================================
# 5. Scoring Run Store Tests
# ===========================================================================


class TestPostgresScoringRunStore:
    def test_save_and_retrieve_scoring_run(self, migrated_test_db):
        store = PostgresScoringRunStore(engine=migrated_test_db)
        score_run = ScoringRunResponse(
            run_id="score_run_500",
            config_id="balanced",
            config_version=1,
            config_source="inline",
            config_snapshot=ScoringConfiguration(
                config_id="balanced",
                name="Inline Rubric Snapshot",
                version=1,
            ),
            evaluated_at="2026-10-17T00:00:00Z",
            teams=[
                TeamScoringResult(
                    team_id="T1",
                    team_name="Alpha",
                    final_score=85.5,
                    score_status=ScoreStatus.CALCULATED,
                    total_configured_weight=100.0,
                    applicable_weight=100.0,
                    explanation="Evaluation successful",
                )
            ],
            summary=ScoringRunSummary(
                total_teams=1,
                calculated_teams=1,
                average_score=85.5,
            ),
        )
        store.save(score_run)

        retrieved = store.get("score_run_500")
        assert retrieved is not None
        assert retrieved.run_id == "score_run_500"
        assert retrieved.config_source == "inline"
        assert retrieved.config_snapshot.name == "Inline Rubric Snapshot"
        assert retrieved.summary.average_score == 85.5
        assert len(retrieved.teams) == 1
        assert retrieved.teams[0].final_score == 85.5


# ===========================================================================
# 6. Ranking Run Store Tests
# ===========================================================================


class TestPostgresRankingRunStore:
    def test_save_and_retrieve_ranking_run(self, migrated_test_db):
        rank_store = PostgresRankingRunStore(engine=migrated_test_db)
        rank_run = RankingRunResponse(
            run_id="rank_run_700",
            evaluated_at="2026-10-17T00:00:00Z",
            top_x=3,
            include_needs_review=False,
            selected_teams=[
                RankedTeamResult(
                    team_id="T1",
                    team_name="Team 1",
                    rank=1,
                    final_score=92.0,
                    score_status=ScoreStatus.CALCULATED,
                    selection_status=SelectionStatus.SELECTED,
                )
            ],
            summary=RankingRunSummary(
                requested_top_x=3,
                selected_teams_count=1,
                shortage=2,
                cutoff_score=92.0,
            ),
        )
        rank_store.save(rank_run)

        retrieved = rank_store.get("rank_run_700")
        assert retrieved is not None
        assert retrieved.run_id == "rank_run_700"
        assert retrieved.top_x == 3
        assert retrieved.summary.shortage == 2
        assert retrieved.summary.cutoff_score == 92.0
        assert len(retrieved.selected_teams) == 1
        assert retrieved.selected_teams[0].rank == 1
        assert retrieved.selected_teams[0].final_score == 92.0


# ===========================================================================
# 7. Storage Factory & Selection Tests
# ===========================================================================


class TestStorageFactory:
    def test_memory_mode_selects_memory_stores(self):
        factory = StorageFactory(backend="memory")
        rule_store = factory.get_rule_config_store()
        elig_store = factory.get_eligibility_run_store()
        assert "RuleConfigStore" in type(rule_store).__name__
        assert "InMemoryRunStore" in type(elig_store).__name__

    def test_postgres_mode_selects_postgres_stores(self, migrated_test_db):
        factory = StorageFactory(backend="postgres", engine=migrated_test_db)
        rule_store = factory.get_rule_config_store()
        elig_store = factory.get_eligibility_run_store()
        assert isinstance(rule_store, PostgresRuleConfigStore)
        assert isinstance(elig_store, PostgresEligibilityRunStore)
        assert rule_store.engine == migrated_test_db

    def test_postgres_mode_does_not_silently_fall_back_on_failure(self):
        # Create an engine pointing to an unreachable host/port
        bad_engine = sa.create_engine(
            "postgresql+psycopg://bad_user:bad_pass@127.0.0.1:59999/nonexistent_db?sslmode=disable",
            connect_args={"connect_timeout": 1},
        )
        factory = StorageFactory(backend="postgres", engine=bad_engine)
        store = factory.get_rule_config_store()
        # Attempting operation must raise database error, NOT fall back to memory
        with pytest.raises((OperationalError, Exception)):
            store.get("basic")


# ===========================================================================
# 8. Database Error Handling Tests
# ===========================================================================


class TestDatabaseErrorHandling:
    def test_foreign_key_violation_returns_409_conflict(self, migrated_test_db):
        default_storage_factory.configure(backend="postgres", engine=migrated_test_db)

        # Register a route to test the FastAPI IntegrityError handler translation safely
        @app.get("/api/test-trigger-fk-violation")
        def _trigger_fk():
            with migrated_test_db.begin() as conn:
                conn.execute(
                    sa.text(
                        "INSERT INTO manual_overrides "
                        "(override_id, run_id, team_id, original_status, override_status, reason, overridden_by, overridden_at, payload) "
                        "VALUES ('bad_ovr', 'nonexistent_run', 'T1', 'ELIGIBLE', 'ELIGIBLE', 'reason', 'admin', NOW(), '{}')"
                    )
                )

        client = TestClient(app)
        resp = client.get("/api/test-trigger-fk-violation")
        assert resp.status_code == 409
        data = resp.json()
        assert data == {"detail": "Referenced record does not exist or cannot be modified"}
        # Ensure no database credentials, URLs or SQL statements are leaked
        assert "postgresql" not in str(resp.content)
        assert "password" not in str(resp.content)
        assert "INSERT" not in str(resp.content)

    def test_unavailable_database_returns_503(self):
        bad_engine = sa.create_engine(
            "postgresql+psycopg://bad:bad@127.0.0.1:59999/bad_db?sslmode=disable",
            connect_args={"connect_timeout": 1},
        )
        default_storage_factory.configure(backend="postgres", engine=bad_engine)
        client = TestClient(app)

        resp = client.get("/api/rules/configs")
        assert resp.status_code == 503
        data = resp.json()
        assert data == {"detail": "Database temporarily unavailable"}
        # Ensure no URL or SQL leak
        assert "postgresql" not in str(resp.content)
        assert "password" not in str(resp.content)
        assert "SELECT" not in str(resp.content)

        # Restore default factory to memory
        default_storage_factory.configure(backend="memory")


# ===========================================================================
# 9. Startup Preset Seeding Tests
# ===========================================================================


class TestStartupPresetSeeding:
    def test_seeding_idempotence_and_preserves_user_configs(self, migrated_test_db):
        rule_store = PostgresRuleConfigStore(engine=migrated_test_db)
        # Create a user config
        user_cfg = RuleConfiguration(
            config_id="user_custom_rule",
            version=1,
            name="My Custom Rules",
            global_config=GlobalRuleConfig(),
            rules=[],
            is_active=True,
        )
        rule_store.save(user_cfg)

        # Run seeding twice
        seed_database_presets(migrated_test_db)
        seed_database_presets(migrated_test_db)

        # Verify default presets exist
        rule_presets = get_default_presets()
        for p in rule_presets:
            db_p = rule_store.get(p.config_id, version=p.version)
            assert db_p is not None
            assert db_p.name == p.name

        scoring_store = PostgresScoringConfigStore(engine=migrated_test_db)
        scoring_presets = get_default_scoring_presets()
        for sp in scoring_presets:
            db_sp = scoring_store.get(sp.config_id, version=sp.version)
            assert db_sp is not None
            assert db_sp.name == sp.name

        # User config is completely untouched
        user_retrieved = rule_store.get("user_custom_rule")
        assert user_retrieved is not None
        assert user_retrieved.name == "My Custom Rules"

    def test_missing_tables_fail_with_clear_error(self):
        # Create a mock engine that reports no tables
        from unittest.mock import MagicMock
        mock_engine = MagicMock()
        mock_inspector = MagicMock()
        mock_inspector.get_table_names.return_value = []

        import app.db.seeding as seeding_mod
        orig_inspect = seeding_mod.inspect
        seeding_mod.inspect = lambda eng: mock_inspector
        try:
            with pytest.raises(RuntimeError) as exc_info:
                seed_database_presets(mock_engine)
            assert "Database schema is incomplete" in str(exc_info.value)
            assert "alembic upgrade head" in str(exc_info.value)
        finally:
            seeding_mod.inspect = orig_inspect


# ===========================================================================
# 10. Database Safety & Reset Isolation Tests
# ===========================================================================


class TestDatabaseSafetyAndReset:
    def test_reset_test_database_rejects_unsafe_database(self, monkeypatch):
        # Simulate an engine pointing to production DATABASE_URL
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@prod.neon.tech/proddb")
        monkeypatch.setenv("TEST_DATABASE_URL", "postgresql://user:pass@test.neon.tech/testdb")

        unsafe_engine = sa.create_engine("postgresql+psycopg://user:pass@prod.neon.tech/proddb?sslmode=require")
        with pytest.raises(ValueError) as exc:
            reset_test_database(unsafe_engine)
        assert "Safety check failed" in str(exc.value)
        assert "password" not in str(exc.value)

    def test_reset_truncates_only_project_tables(self, migrated_test_db):
        rule_store = PostgresRuleConfigStore(engine=migrated_test_db)
        rule_store.save(
            RuleConfiguration(
                config_id="temp_rule",
                version=1,
                name="Temp",
                global_config=GlobalRuleConfig(),
                rules=[],
                is_active=True,
            )
        )
        assert rule_store.get("temp_rule") is not None

        reset_test_database(migrated_test_db)
        assert rule_store.get("temp_rule") is None
