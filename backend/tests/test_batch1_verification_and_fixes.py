"""Tests for Batch 1 fixes:
1. RuleDefinition parameter synchronization (parameters vs top-level precedence)
2. Manual eligibility override + rerun ranking rescoring disqualified teams
3. Preservation of is_unresolved and is_temporary_id on TeamScoringResult through to ranking
4. Multi-tenant config_id collision disambiguation
5. TrackLimitEvaluator multiple member resolution
6. GitHubAnalyzer cache bounding, clear_cache, and github_token handling
"""

import io
import pytest
from starlette.testclient import TestClient

from app.auth.jwt import create_access_token
from app.main import app
from app.rules.schemas import (
    AggregationMethod,
    EligibilityStatus,
    GlobalRuleConfig,
    MemberSelection,
    OnMissingAction,
    RuleConfiguration,
    RuleDefinition,
    RuleResultStatus,
    RuleScope,
    RuleSeverity,
)
from app.rules.types.signal_threshold import SignalThresholdEvaluator
from app.rules.types.track_limit import _resolve_team_track
from app.schemas.auth import UserSchema
from app.schemas.ingestion import MemberSchema, TeamSchema
from app.scoring.engine import calculate_team_score, evaluate_scoring
from app.scoring.schemas import (
    EvaluationCriterion,
    NormalizationConfig,
    ScoreStatus,
    ScoringConfiguration,
)
from app.signals.github import GitHubAnalyzer
from app.signals.schemas import ExtractedSignal, SignalEvidence, SignalStatus
from app.storage import default_storage_factory, default_user_store

client = TestClient(app)


# ---------------------------------------------------------------------------
# Issue 1: RuleDefinition Parameter Synchronization
# ---------------------------------------------------------------------------

def test_rule_definition_parameters_precedence_and_sync():
    """RuleDefinition model validator synchronizes member_selection and aggregation."""
    # 1. parameters wins when supplied (e.g. from UI edit modal)
    rule_dict = {
        "rule_id": "r1",
        "rule_type": "signal_threshold",
        "name": "CGPA Rule",
        "member_selection": "all_members",
        "aggregation": "all",
        "parameters": {
            "signal_key": "academic_cgpa",
            "operator": ">=",
            "threshold": 7.0,
            "member_selection": "any_member",
            "aggregation": "max",
        },
    }
    rule = RuleDefinition.model_validate(rule_dict)
    assert rule.member_selection == MemberSelection.ANY_MEMBER
    assert rule.aggregation == AggregationMethod.MAX
    assert rule.parameters["member_selection"] == "any_member"
    assert rule.parameters["aggregation"] == "max"

    # 2. top-level populates parameters if parameters omitted
    rule_top_level = RuleDefinition(
        rule_id="r2",
        rule_type="signal_threshold",
        name="CGPA Rule 2",
        member_selection=MemberSelection.TEAM_LEAD,
        aggregation=AggregationMethod.MEAN,
    )
    assert rule_top_level.parameters.get("member_selection") == "team_lead"
    assert rule_top_level.parameters.get("aggregation") == "mean"


def test_signal_threshold_evaluator_respects_updated_parameters():
    """Evaluator properly uses synchronized parameters to evaluate."""
    evaluator = SignalThresholdEvaluator()
    rule = RuleDefinition(
        rule_id="r_cgpa",
        rule_type="signal_threshold",
        name="Min CGPA",
        severity=RuleSeverity.HARD,
        scope=RuleScope.MEMBER,
        parameters={
            "signal_key": "academic_cgpa",
            "operator": ">=",
            "threshold": 7.0,
            "member_selection": "any_member",
            "aggregation": "max",
        },
    )
    team = TeamSchema(
        team_id="t1",
        team_name="Team Alpha",
        members=[
            MemberSchema(member_id="m1", name="Alice"),
            MemberSchema(member_id="m2", name="Bob"),
        ],
    )
    # Alice has CGPA 6.0 (fails threshold), Bob has 8.5 (satisfies threshold)
    signals = {
        "m1": {
            "academic_cgpa": ExtractedSignal(
                signal_key="academic_cgpa",
                category="academic",
                value=6.0,
                status=SignalStatus.EXTRACTED,
                evidence=SignalEvidence(source="form", raw_input="6.0"),
            )
        },
        "m2": {
            "academic_cgpa": ExtractedSignal(
                signal_key="academic_cgpa",
                category="academic",
                value=8.5,
                status=SignalStatus.EXTRACTED,
                evidence=SignalEvidence(source="form", raw_input="8.5"),
            )
        },
    }
    result = evaluator.evaluate(rule, team, signals, GlobalRuleConfig())
    # Because member_selection is any_member, Bob satisfying threshold means PASSED
    assert result.status == RuleResultStatus.PASSED


# ---------------------------------------------------------------------------
# Issue 2: Manual Eligibility Override + Rerun Ranking Rescores Disqualified Teams
# ---------------------------------------------------------------------------

def test_manual_override_rescores_disqualified_team_in_ranking():
    """When an ineligible disqualified team is manually overridden to eligible,
    ranking re-scores the team with criteria breakdowns instead of keeping it disqualified.
    """
    csv_data = (
        "team_id,team_name,member_id,name,email,cgpa\n"
        "T1,Solo Ineligible,M1,Alice,alice@test.org,9.0\n"
        "T2,Duo Eligible,M2,Bob,bob@test.org,8.0\n"
        "T2,Duo Eligible,M3,Charlie,charlie@test.org,8.5\n"
    )
    upload_resp = client.post(
        "/api/ingestion/upload",
        files={"file": ("teams.csv", io.BytesIO(csv_data.encode()), "text/csv")},
    )
    assert upload_resp.status_code == 200
    dataset_id = upload_resp.json()["dataset_id"]

    # Extract signals
    ext_resp = client.post(
        "/api/signals/extract",
        json={"dataset_id": dataset_id, "signal_keys": ["academic_cgpa"]},
    )
    assert ext_resp.status_code == 200
    ext_run_id = ext_resp.json()["run_id"]

    # Run eligibility with 'basic' preset (requires min_size=2)
    # T1 will be INELIGIBLE (1 member < 2), T2 will be ELIGIBLE (2 members)
    elig_resp = client.post(
        "/api/rules/evaluate",
        json={"dataset_id": dataset_id, "config_id": "basic"},
    )
    assert elig_resp.status_code == 200
    elig_run_id = elig_resp.json()["run_id"]

    # Create scoring config with score_ineligible_teams=False
    cfg_resp = client.post(
        "/api/scoring/configs",
        json={
            "config_id": "cfg_disqualify_ineligible",
            "name": "Disqualify Ineligible Rubric",
            "score_ineligible_teams": False,
            "scale_max": 100.0,
            "criteria": [
                {
                    "criterion_id": "crit_cgpa",
                    "name": "Academic CGPA",
                    "criterion_type": "numeric_range",
                    "target_signal_key": "academic_cgpa",
                    "weight": 10.0,
                    "normalization": {"linear_range": {"min_value": 0, "max_value": 10}},
                }
            ],
        },
    )
    assert cfg_resp.status_code == 201

    # Run scoring with score_ineligible_teams=False
    # T1 gets score_status=DISQUALIFIED and final_score=0.0
    scoring_resp = client.post(
        "/api/scoring/evaluate",
        json={
            "dataset_id": dataset_id,
            "extraction_run_id": ext_run_id,
            "eligibility_run_id": elig_run_id,
            "config_id": "cfg_disqualify_ineligible",
        },
    )
    assert scoring_resp.status_code == 200
    scoring_run_id = scoring_resp.json()["run_id"]
    t1_score = next(t for t in scoring_resp.json()["teams"] if t["team_id"] == "T1")
    assert t1_score["score_status"] == "DISQUALIFIED"
    assert t1_score["final_score"] == 0.0

    # Apply manual override for T1: INELIGIBLE -> ELIGIBLE
    override_resp = client.post(
        f"/api/rules/runs/{elig_run_id}/teams/T1/override",
        json={
            "override_status": "ELIGIBLE",
            "reason": "Solo participation authorized by organizer.",
            "overridden_by": "lead_organizer",
        },
    )
    assert override_resp.status_code == 200

    # Rerun ranking with the existing scoring_run_id and eligibility_run_id
    ranking_resp = client.post(
        "/api/ranking/evaluate",
        json={
            "scoring_run_id": scoring_run_id,
            "eligibility_run_id": elig_run_id,
            "top_x": 5,
        },
    )
    assert ranking_resp.status_code == 200
    ranking_data = ranking_resp.json()

    # Verify T1 is no longer disqualified and is placed in leaderboard
    ranked_team_ids = [t["team_id"] for t in ranking_data["ranked_teams"]]
    assert "T1" in ranked_team_ids

    t1_ranked = next(t for t in ranking_data["ranked_teams"] if t["team_id"] == "T1")
    assert t1_ranked["score_status"] == "CALCULATED"
    assert t1_ranked["eligibility_status"] == "ELIGIBLE"
    assert t1_ranked["final_score"] > 0.0


# ---------------------------------------------------------------------------
# Issue 3: Preservation of is_unresolved and is_temporary_id
# ---------------------------------------------------------------------------

def test_scoring_preserves_unresolved_and_temporary_id():
    """TeamScoringResult preserves is_unresolved and is_temporary_id from ingestion."""
    team = TeamSchema(
        team_id="temp_t1_abc",
        team_name="Duplicate Team",
        is_temporary_id=True,
        is_unresolved=True,
        members=[MemberSchema(member_id="m1", name="Alice")],
    )
    config = ScoringConfiguration(
        config_id="c1",
        version=1,
        name="Test Rubric",
        criteria=[
            EvaluationCriterion(
                criterion_id="crit_dummy",
                name="Dummy",
                criterion_type="numeric_range",
                target_signal_key="dummy_sig",
                weight=10.0,
                normalization=NormalizationConfig(),
            )
        ],
    )
    res = calculate_team_score(
        team=team,
        config=config,
        signals_by_member={},
        eligibility_status=EligibilityStatus.ELIGIBLE,
    )
    assert res.is_temporary_id is True
    assert res.is_unresolved is True


# ---------------------------------------------------------------------------
# Issue 4: Multi-Tenant Config Creation Disambiguation
# ---------------------------------------------------------------------------

def test_cross_tenant_config_creation_with_same_id(monkeypatch):
    """User B creating a config with the same custom ID as User A succeeds without 409 collision."""
    monkeypatch.setattr("app.auth.dependencies.AUTH_ENABLED", True)
    monkeypatch.setattr("app.api.endpoints.scoring.AUTH_ENABLED", True)
    monkeypatch.setattr("app.api.endpoints.rules.AUTH_ENABLED", True)
    monkeypatch.setattr("app.config.AUTH_ENABLED", True)
    default_storage_factory.configure(backend="memory")
    default_user_store.reset()

    # Setup User A
    alice = UserSchema(user_id="usr_alice", email="alice@test.org", name="Alice", is_active=True)
    default_user_store.save(alice)
    alice_token = create_access_token({"sub": "usr_alice", "email": "alice@test.org", "name": "Alice"})
    alice_headers = {"Authorization": f"Bearer {alice_token}"}

    # Setup User B
    bob = UserSchema(user_id="usr_bob", email="bob@test.org", name="Bob", is_active=True)
    default_user_store.save(bob)
    bob_token = create_access_token({"sub": "usr_bob", "email": "bob@test.org", "name": "Bob"})
    bob_headers = {"Authorization": f"Bearer {bob_token}"}

    scoring_payload = {
        "config_id": "shared_model_slug",
        "name": "Custom Model",
        "scale_max": 100.0,
        "criteria": [
            {
                "criterion_id": "c1",
                "name": "Criterion 1",
                "criterion_type": "numeric_range",
                "target_signal_key": "github_public_repo_count",
                "weight": 100.0,
                "normalization": {
                    "linear_range": {"min_value": 0, "max_value": 20}
                },
            }
        ],
    }

    # 1. Alice creates scoring config 'shared_model_slug'
    resp_a = client.post("/api/scoring/configs", json=scoring_payload, headers=alice_headers)
    assert resp_a.status_code == 201
    assert resp_a.json()["config_id"] == "shared_model_slug"

    # 2. Bob creates scoring config with same 'shared_model_slug' -> must NOT 409 conflict
    resp_b = client.post("/api/scoring/configs", json=scoring_payload, headers=bob_headers)
    assert resp_b.status_code == 201
    bob_config_id = resp_b.json()["config_id"]
    # Bob gets a disambiguated unique config_id that doesn't collide
    assert "shared_model_slug" in bob_config_id

    # 3. Bob can retrieve his config
    bob_get = client.get(f"/api/scoring/configs/{bob_config_id}", headers=bob_headers)
    assert bob_get.status_code == 200


# ---------------------------------------------------------------------------
# Issue 5: GitHubAnalyzer Cache Bounding, clear_cache & github_token
# ---------------------------------------------------------------------------

def test_github_analyzer_cache_bounding_clear_and_token():
    """GitHubAnalyzer clears cache, bounds size, and honors config github_token."""
    analyzer = GitHubAnalyzer()

    # Test cache insertion and clear_cache
    analyzer._set_cache_entry(analyzer._user_cache, "user1", {"login": "user1"})
    assert "user1" in analyzer._user_cache

    analyzer.clear_cache()
    assert len(analyzer._user_cache) == 0

    # Test FIFO cache eviction with small max_size
    for i in range(10):
        analyzer._set_cache_entry(analyzer._user_cache, f"user_{i}", {"id": i}, max_size=5)
    assert len(analyzer._user_cache) == 5
    # Oldest entries 0-4 should have been evicted
    assert "user_0" not in analyzer._user_cache
    assert "user_9" in analyzer._user_cache

    # Test token passed to client
    custom_client = analyzer._get_client(token="pat_override_12345")
    assert "Authorization" in custom_client.headers
    assert "pat_override_12345" in custom_client.headers["Authorization"]


# ---------------------------------------------------------------------------
# Issue 6: TrackLimitEvaluator Multi-Member Resolution
# ---------------------------------------------------------------------------

def test_track_limit_evaluator_checks_all_members():
    """TrackLimitEvaluator._resolve_team_track checks all members when member 0 is not_provided."""
    team = TeamSchema(
        team_id="t1",
        team_name="Team Multitrack",
        members=[
            MemberSchema(member_id="m1", name="Member 1", custom_fields={"track": ""}),
            MemberSchema(member_id="m2", name="Member 2", custom_fields={"track": "AI Track"}),
        ],
    )
    val, state = _resolve_team_track(team, "track")
    assert state == "present"
    assert val == "AI Track"


# ---------------------------------------------------------------------------
# Batch 3: ExcludedTeamResult Criteria Breakdowns Preservation
# ---------------------------------------------------------------------------

def test_excluded_team_preserves_criteria_breakdowns_when_informational_scoring():
    """Batch 3 Issue 2: When score_ineligible_teams=True, ineligible excluded teams
    preserve criteria_breakdowns, weight_renormalized, applicable_weight, and total_configured_weight.
    """
    csv_data = (
        "team_id,team_name,member_id,name,email,cgpa,github\n"
        "T_EXCL,Solo Ineligible,M1,Alice,alice@test.org,9.0,https://github.com/alice\n"
        "T_VALID,Duo Eligible,M2,Bob,bob@test.org,8.0,https://github.com/bob\n"
        "T_VALID,Duo Eligible,M3,Charlie,charlie@test.org,8.5,https://github.com/charlie\n"
    )
    upload_resp = client.post(
        "/api/ingestion/upload",
        files={"file": ("teams.csv", io.BytesIO(csv_data.encode()), "text/csv")},
    )
    assert upload_resp.status_code == 200
    dataset_id = upload_resp.json()["dataset_id"]

    ext_resp = client.post(
        "/api/signals/extract",
        json={"dataset_id": dataset_id, "signal_keys": ["academic_cgpa"]},
    )
    assert ext_resp.status_code == 200
    ext_run_id = ext_resp.json()["run_id"]

    # Basic preset requires team_size >= 2, so T_EXCL will be INELIGIBLE
    elig_resp = client.post(
        "/api/rules/evaluate",
        json={"dataset_id": dataset_id, "config_id": "basic"},
    )
    assert elig_resp.status_code == 200
    elig_run_id = elig_resp.json()["run_id"]

    # Create scoring config with score_ineligible_teams=True (informational scoring)
    cfg_resp = client.post(
        "/api/scoring/configs",
        json={
            "config_id": "cfg_info_scoring_batch3",
            "name": "Informational Scoring Rubric",
            "score_ineligible_teams": True,
            "scale_max": 100.0,
            "criteria": [
                {
                    "criterion_id": "crit_cgpa_b3",
                    "name": "Academic CGPA",
                    "criterion_type": "numeric_range",
                    "target_signal_key": "academic_cgpa",
                    "weight": 10.0,
                    "normalization": {"linear_range": {"min_value": 0, "max_value": 10}},
                }
            ],
        },
    )
    assert cfg_resp.status_code == 201

    scoring_resp = client.post(
        "/api/scoring/evaluate",
        json={
            "dataset_id": dataset_id,
            "extraction_run_id": ext_run_id,
            "eligibility_run_id": elig_run_id,
            "config_id": "cfg_info_scoring_batch3",
        },
    )
    assert scoring_resp.status_code == 200
    scoring_run_id = scoring_resp.json()["run_id"]
    t_excl_score = next(t for t in scoring_resp.json()["teams"] if t["team_id"] == "T_EXCL")
    assert t_excl_score["score_status"] == "CALCULATED"
    assert t_excl_score["final_score"] is not None
    assert len(t_excl_score["criteria_breakdowns"]) > 0

    # Evaluate ranking (with include_needs_review=True so T_VALID qualifies despite missing profile link)
    ranking_resp = client.post(
        "/api/ranking/evaluate",
        json={
            "scoring_run_id": scoring_run_id,
            "eligibility_run_id": elig_run_id,
            "top_x": 1,
            "include_needs_review": True,
        },
    )
    assert ranking_resp.status_code == 200
    rank_data = ranking_resp.json()
    assert len(rank_data["selected_teams"]) == 1
    assert rank_data["selected_teams"][0]["team_id"] == "T_VALID"

    # T_EXCL must be in excluded_teams with criteria_breakdowns preserved
    assert len(rank_data["excluded_teams"]) == 1
    excl = rank_data["excluded_teams"][0]
    assert excl["team_id"] == "T_EXCL"
    assert excl["reason_code"] == "INELIGIBLE"
    assert len(excl["criteria_breakdowns"]) == 1
    assert excl["criteria_breakdowns"][0]["criterion_id"] == "crit_cgpa_b3"
    assert excl["criteria_breakdowns"][0]["team_criterion_score"] is not None
    assert excl["applicable_weight"] == 10.0
    assert excl["total_configured_weight"] == 10.0
