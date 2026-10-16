"""Comprehensive test suite for Phase 6: Ranking, Top-X Selection, and Explainable Shortlisting.

Covers all 30 requirements specified in Phase 6:
1-6: Ranking (descending score, tiebreak criterion, team_id, missing tiebreak handling, determinism, 0.0 scores)
7-11: Top-X Selection (exact top_x, shortage, negative/zero/invalid validation, cutoff tie warning, no shortlist expansion)
12-20: Status Handling (INELIGIBLE, NEEDS_REVIEW, include_needs_review, NO_SCORE, DISQUALIFIED, cannot bypass, UNRESOLVED, missing eligibility warning, 0.0 not confused with NO_SCORE)
21-25: Explanations (score breakdowns preserved, reason codes, completeness info, shortage warnings, review suggestions non-approving)
26-30: Integration & API (API endpoints, run traceability, scoring run retrieval, no recalculation, existing contracts)
"""

from __future__ import annotations

from typing import Any, Optional
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ranking.engine import evaluate_ranking, extract_tiebreak_score, is_unresolved_team
from app.ranking.schemas import (
    ExclusionReason,
    RankedTeamResult,
    RankingEvaluationRequest,
    RankingRunResponse,
    SelectionStatus,
)
from app.ranking.store import default_ranking_run_store
from app.rules.config_store import default_config_store
from app.rules.schemas import EligibilityStatus
from app.rules.store import default_override_store, default_run_store
from app.scoring.config_store import default_scoring_config_store
from app.scoring.schemas import (
    CriterionScoreBreakdown,
    CriterionType,
    MissingDataPolicy,
    ScoreStatus,
    ScoringRunResponse,
    ScoringRunSummary,
    TeamScoringResult,
)
from app.scoring.store import default_scoring_run_store

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures & Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_all_stores():
    """Ensure clean store state before and after each test."""
    default_config_store.reset()
    default_run_store.reset()
    default_override_store.reset()
    default_scoring_config_store.reset()
    default_scoring_run_store.reset()
    default_ranking_run_store.reset()
    yield
    default_config_store.reset()
    default_run_store.reset()
    default_override_store.reset()
    default_scoring_config_store.reset()
    default_scoring_run_store.reset()
    default_ranking_run_store.reset()


def make_breakdown(
    criterion_id: str,
    team_criterion_score: Optional[float] = 0.8,
    is_applicable: bool = True,
    weighted_contribution: float = 25.0,
    target_signal_key: Optional[str] = None,
) -> CriterionScoreBreakdown:
    """Helper to create a populated CriterionScoreBreakdown."""
    return CriterionScoreBreakdown(
        criterion_id=criterion_id,
        name=f"Criterion {criterion_id}",
        target_signal_key=target_signal_key or criterion_id,
        criterion_type=CriterionType.NUMERIC_RANGE,
        configured_weight=25.0,
        normalized_weight=0.25,
        normalization_method="linear_range",
        aggregation_method="mean",
        team_criterion_score=team_criterion_score,
        weighted_contribution=weighted_contribution,
        missing_data_policy=MissingDataPolicy.EXCLUDE_AND_RENORMALIZE,
        is_applicable=is_applicable,
        explanation=f"Evaluated {criterion_id}: score={team_criterion_score}",
    )


def make_scored_team(
    team_id: str,
    final_score: Optional[float] = 75.0,
    score_status: ScoreStatus = ScoreStatus.CALCULATED,
    eligibility_status: Optional[EligibilityStatus] = EligibilityStatus.ELIGIBLE,
    eligibility_summary: Optional[str] = None,
    team_name: Optional[str] = None,
    criteria_breakdowns: Optional[list[CriterionScoreBreakdown]] = None,
    weight_renormalized: bool = False,
    applicable_weight: float = 100.0,
    warnings: Optional[list[str]] = None,
) -> TeamScoringResult:
    """Helper to create a populated TeamScoringResult."""
    return TeamScoringResult(
        team_id=team_id,
        team_name=team_name or f"Team {team_id}",
        final_score=final_score,
        score_status=score_status,
        total_configured_weight=100.0,
        applicable_weight=applicable_weight,
        weight_renormalized=weight_renormalized,
        criteria_breakdowns=criteria_breakdowns or [],
        eligibility_status=eligibility_status,
        eligibility_summary=eligibility_summary,
        warnings=warnings or [],
        explanation=f"Calculated composite score: {final_score}",
    )


# ===========================================================================
# 1. RANKING LOGIC (Cases 1-6)
# ===========================================================================


def test_ranking_descending_final_score():
    """Case 1: Teams are ranked by descending final score."""
    teams = [
        make_scored_team("team_b", final_score=60.0),
        make_scored_team("team_a", final_score=95.0),
        make_scored_team("team_c", final_score=80.0),
    ]
    res = evaluate_ranking(teams, top_x=3)
    assert [t.team_id for t in res.ranked_teams] == ["team_a", "team_c", "team_b"]
    assert [t.rank for t in res.ranked_teams] == [1, 2, 3]
    assert [t.final_score for t in res.ranked_teams] == [95.0, 80.0, 60.0]


def test_ranking_equal_scores_resolved_by_tiebreak_criterion():
    """Case 2: Equal primary final scores are resolved by the configured tiebreak criterion."""
    teams = [
        make_scored_team(
            "team_1",
            final_score=80.0,
            criteria_breakdowns=[make_breakdown("crit_tech", team_criterion_score=0.6)],
        ),
        make_scored_team(
            "team_2",
            final_score=80.0,
            criteria_breakdowns=[make_breakdown("crit_tech", team_criterion_score=0.9)],
        ),
        make_scored_team(
            "team_3",
            final_score=80.0,
            criteria_breakdowns=[make_breakdown("crit_tech", team_criterion_score=0.75)],
        ),
    ]
    res = evaluate_ranking(teams, top_x=3, tiebreak_criterion_id="crit_tech")
    assert [t.team_id for t in res.ranked_teams] == ["team_2", "team_3", "team_1"]
    assert all(t.is_tied for t in res.ranked_teams)
    assert res.ranked_teams[0].tiebreak_score == 0.9


def test_ranking_equal_scores_resolved_by_team_id():
    """Case 3: Equal final scores (without tiebreak or with equal tiebreak) sort by team_id ascending."""
    teams = [
        make_scored_team("gamma", final_score=85.0),
        make_scored_team("alpha", final_score=85.0),
        make_scored_team("beta", final_score=85.0),
    ]
    res = evaluate_ranking(teams, top_x=3)
    assert [t.team_id for t in res.ranked_teams] == ["alpha", "beta", "gamma"]
    assert all(t.is_tied for t in res.ranked_teams)


def test_ranking_missing_tiebreak_criterion_handled_correctly():
    """Case 4: Teams with available tiebreak scores rank before teams with missing tiebreak scores."""
    teams = [
        make_scored_team(
            "team_missing_1",
            final_score=80.0,
            criteria_breakdowns=[make_breakdown("crit_tech", team_criterion_score=None)],
        ),
        make_scored_team(
            "team_with_score",
            final_score=80.0,
            criteria_breakdowns=[make_breakdown("crit_tech", team_criterion_score=0.3)],
        ),
        make_scored_team(
            "team_missing_2",
            final_score=80.0,
            criteria_breakdowns=[],
        ),
    ]
    res = evaluate_ranking(teams, top_x=3, tiebreak_criterion_id="crit_tech")
    # team_with_score has score 0.3 -> comes first.
    # team_missing_1 and team_missing_2 both lack score -> sort by team_id ("team_missing_1" < "team_missing_2").
    assert [t.team_id for t in res.ranked_teams] == ["team_with_score", "team_missing_1", "team_missing_2"]


def test_ranking_deterministic_identical_inputs():
    """Case 5: Identical inputs produce identical rankings regardless of input order."""
    teams_1 = [
        make_scored_team("t1", final_score=70.0),
        make_scored_team("t2", final_score=90.0),
        make_scored_team("t3", final_score=80.0),
    ]
    teams_2 = [
        make_scored_team("t3", final_score=80.0),
        make_scored_team("t1", final_score=70.0),
        make_scored_team("t2", final_score=90.0),
    ]
    res_1 = evaluate_ranking(teams_1, top_x=3)
    res_2 = evaluate_ranking(teams_2, top_x=3)

    assert [t.team_id for t in res_1.ranked_teams] == [t.team_id for t in res_2.ranked_teams]
    assert [t.rank for t in res_1.ranked_teams] == [t.rank for t in res_2.ranked_teams]


def test_ranking_legitimate_zero_score_is_valid():
    """Case 6: Legitimate numerical 0.0 scores participate in ranking and are not dropped."""
    teams = [
        make_scored_team("team_high", final_score=50.0),
        make_scored_team("team_zero", final_score=0.0, score_status=ScoreStatus.CALCULATED),
    ]
    res = evaluate_ranking(teams, top_x=2)
    assert len(res.selected_teams) == 2
    assert res.ranked_teams[1].team_id == "team_zero"
    assert res.ranked_teams[1].final_score == 0.0
    assert res.ranked_teams[1].rank == 2


# ===========================================================================
# 2. TOP-X SELECTION (Cases 7-11)
# ===========================================================================


def test_top_x_exact_qualifying_teams_returned():
    """Case 7: Exactly top_x qualifying teams are returned when enough qualify."""
    teams = [make_scored_team(f"team_{i}", final_score=float(100 - i)) for i in range(10)]
    res = evaluate_ranking(teams, top_x=5)
    assert len(res.selected_teams) == 5
    assert len(res.ranked_teams) == 10
    assert res.summary.selected_teams_count == 5
    assert res.summary.shortage == 0
    assert [t.rank for t in res.selected_teams] == [1, 2, 3, 4, 5]


def test_top_x_fewer_teams_returned_when_insufficient():
    """Case 8: When fewer teams qualify than top_x, return available qualifying teams with shortage warning."""
    teams = [
        make_scored_team("team_1", final_score=90.0),
        make_scored_team("team_2", final_score=85.0),
    ]
    res = evaluate_ranking(teams, top_x=5)
    assert len(res.selected_teams) == 2
    assert res.summary.shortage == 3
    assert any("Shortage: Requested top_x=5, but only 2 qualifying team(s)" in w for w in res.warnings)


def test_top_x_invalid_values_rejected():
    """Case 9: Zero, negative, and invalid top_x values are rejected."""
    teams = [make_scored_team("team_1", final_score=90.0)]
    with pytest.raises(ValueError, match="top_x must be a positive integer"):
        evaluate_ranking(teams, top_x=0)

    with pytest.raises(ValueError, match="top_x must be a positive integer"):
        evaluate_ranking(teams, top_x=-3)

    # API validation returns 422
    resp_zero = client.post("/api/ranking/evaluate", json={"top_x": 0, "scoring_results": [teams[0].model_dump()]})
    assert resp_zero.status_code == 422

    resp_neg = client.post("/api/ranking/evaluate", json={"top_x": -5, "scoring_results": [teams[0].model_dump()]})
    assert resp_neg.status_code == 422


def test_top_x_tie_at_cutoff_produces_warning():
    """Case 10: Tie at the cutoff boundary sets tie_at_cutoff=True and produces an explanatory warning."""
    teams = [
        make_scored_team("team_1", final_score=90.0),
        make_scored_team("team_2", final_score=85.0),
        make_scored_team("team_3", final_score=80.0),  # 3rd position (last in top_x=3)
        make_scored_team("team_4", final_score=80.0),  # 4th position (tied with 3rd!)
        make_scored_team("team_5", final_score=70.0),
    ]
    res = evaluate_ranking(teams, top_x=3)
    assert res.summary.tie_at_cutoff is True
    assert any("Tie at Top-3 cutoff" in w for w in res.warnings)


def test_top_x_cutoff_tie_does_not_silently_expand_shortlist():
    """Case 11: Cutoff tie does not silently expand shortlist beyond top_x."""
    teams = [
        make_scored_team("team_a", final_score=90.0),
        make_scored_team("team_b", final_score=80.0),
        make_scored_team("team_c", final_score=80.0),
        make_scored_team("team_d", final_score=80.0),
    ]
    res = evaluate_ranking(teams, top_x=2)
    assert len(res.selected_teams) == 2
    assert res.summary.selected_teams_count == 2
    assert res.summary.tie_at_cutoff is True


# ===========================================================================
# 3. STATUS HANDLING (Cases 12-20)
# ===========================================================================


def test_status_ineligible_excluded_by_default():
    """Case 12: INELIGIBLE teams are excluded by default with reason code INELIGIBLE."""
    teams = [
        make_scored_team("t_elig", final_score=90.0, eligibility_status=EligibilityStatus.ELIGIBLE),
        make_scored_team(
            "t_inelig",
            final_score=99.0,
            eligibility_status=EligibilityStatus.INELIGIBLE,
            eligibility_summary="Required link missing",
        ),
    ]
    res = evaluate_ranking(teams, top_x=2)
    assert len(res.selected_teams) == 1
    assert res.selected_teams[0].team_id == "t_elig"

    inelig_excl = next(e for e in res.excluded_teams if e.team_id == "t_inelig")
    assert inelig_excl.reason_code == ExclusionReason.INELIGIBLE
    assert "Required link missing" in inelig_excl.explanation
    assert inelig_excl.final_score == 99.0


def test_status_needs_review_separated_by_default():
    """Case 13: Scored NEEDS_REVIEW teams are placed in needs_review_teams, not in selected_teams."""
    teams = [
        make_scored_team("t_elig", final_score=85.0, eligibility_status=EligibilityStatus.ELIGIBLE),
        make_scored_team(
            "t_review",
            final_score=95.0,
            eligibility_status=EligibilityStatus.NEEDS_REVIEW,
            eligibility_summary="Manual review for CGPA",
        ),
    ]
    res = evaluate_ranking(teams, top_x=2)
    assert len(res.selected_teams) == 1
    assert res.selected_teams[0].team_id == "t_elig"

    assert len(res.needs_review_teams) == 1
    rev_team = res.needs_review_teams[0]
    assert rev_team.team_id == "t_review"
    assert rev_team.final_score == 95.0
    assert rev_team.selection_status == SelectionStatus.NEEDS_REVIEW
    assert "Manual review for CGPA" in rev_team.explanation


def test_status_needs_review_included_when_flag_true():
    """Case 14: Scored NEEDS_REVIEW teams can participate when include_needs_review is True."""
    teams = [
        make_scored_team("t_elig", final_score=80.0, eligibility_status=EligibilityStatus.ELIGIBLE),
        make_scored_team("t_review", final_score=95.0, eligibility_status=EligibilityStatus.NEEDS_REVIEW),
    ]
    res = evaluate_ranking(teams, top_x=2, include_needs_review=True)
    assert len(res.selected_teams) == 2
    # t_review had higher score, ranks #1
    assert res.selected_teams[0].team_id == "t_review"
    assert res.selected_teams[0].rank == 1
    # Underlying eligibility status must NOT be altered
    assert res.selected_teams[0].eligibility_status == EligibilityStatus.NEEDS_REVIEW
    assert "include_needs_review=True" in res.selected_teams[0].explanation


def test_status_no_score_excluded():
    """Case 15: Teams with NO_SCORE or final_score=None are excluded with reason code NO_SCORE."""
    teams = [
        make_scored_team("t_valid", final_score=70.0),
        make_scored_team("t_no_score", final_score=None, score_status=ScoreStatus.NO_SCORE),
    ]
    res = evaluate_ranking(teams, top_x=2)
    assert len(res.selected_teams) == 1
    assert res.selected_teams[0].team_id == "t_valid"

    excl = next(e for e in res.excluded_teams if e.team_id == "t_no_score")
    assert excl.reason_code == ExclusionReason.NO_SCORE


def test_status_disqualified_excluded():
    """Case 16: Teams with DISQUALIFIED status are excluded with reason code DISQUALIFIED."""
    teams = [
        make_scored_team("t_valid", final_score=70.0),
        make_scored_team("t_disq", final_score=0.0, score_status=ScoreStatus.DISQUALIFIED),
    ]
    res = evaluate_ranking(teams, top_x=2)
    assert len(res.selected_teams) == 1
    excl = next(e for e in res.excluded_teams if e.team_id == "t_disq")
    assert excl.reason_code == ExclusionReason.DISQUALIFIED


def test_status_general_inclusion_cannot_bypass_disqualified():
    """Case 17: include_needs_review=True cannot bypass DISQUALIFIED or INELIGIBLE status."""
    teams = [
        make_scored_team(
            "t_disq_review",
            final_score=95.0,
            score_status=ScoreStatus.DISQUALIFIED,
            eligibility_status=EligibilityStatus.NEEDS_REVIEW,
        ),
        make_scored_team(
            "t_inelig_review",
            final_score=90.0,
            score_status=ScoreStatus.CALCULATED,
            eligibility_status=EligibilityStatus.INELIGIBLE,
        ),
    ]
    res = evaluate_ranking(teams, top_x=2, include_needs_review=True)
    assert len(res.selected_teams) == 0
    assert len(res.excluded_teams) == 2


def test_status_unresolved_identities_excluded():
    """Case 18: Unresolved team identities (temp_team_... or is_unresolved=True) are excluded."""
    teams = [
        make_scored_team("team_valid", final_score=80.0),
        make_scored_team(
            "temp_team_warriors_a1b2_unresolved_1",
            final_score=90.0,
            team_name="Warriors",
        ),
    ]
    res = evaluate_ranking(teams, top_x=2)
    assert len(res.selected_teams) == 1
    assert res.selected_teams[0].team_id == "team_valid"

    assert len(res.unresolved_teams) == 1
    assert res.unresolved_teams[0].reason_code == ExclusionReason.UNRESOLVED


def test_status_missing_eligibility_produces_warning():
    """Case 19: Missing eligibility data allows score ranking but returns a clear warning."""
    teams = [
        make_scored_team("t1", final_score=85.0, eligibility_status=None),
        make_scored_team("t2", final_score=75.0, eligibility_status=None),
    ]
    res = evaluate_ranking(teams, top_x=2)
    assert len(res.selected_teams) == 2
    assert any("Eligibility was not evaluated" in w for w in res.warnings)
    assert res.selected_teams[0].eligibility_status is None


def test_status_valid_zero_not_confused_with_no_score():
    """Case 20: Genuine 0.0 scores are not confused with NO_SCORE and qualify for selection."""
    teams = [
        make_scored_team("t_zero", final_score=0.0, score_status=ScoreStatus.CALCULATED),
        make_scored_team("t_none", final_score=None, score_status=ScoreStatus.NO_SCORE),
    ]
    res = evaluate_ranking(teams, top_x=2)
    assert len(res.selected_teams) == 1
    assert res.selected_teams[0].team_id == "t_zero"
    assert res.selected_teams[0].final_score == 0.0

    assert len(res.excluded_teams) == 1
    assert res.excluded_teams[0].team_id == "t_none"


# ===========================================================================
# 4. EXPLANATIONS & AUDIT TRAIL (Cases 21-25)
# ===========================================================================


def test_explanations_selected_teams_contain_score_breakdown():
    """Case 21: Selected teams preserve criteria breakdowns and explanations."""
    breakdowns = [
        make_breakdown("github_repos", team_criterion_score=0.9, weighted_contribution=35.0),
        make_breakdown("academic_cgpa", team_criterion_score=0.8, weighted_contribution=35.0),
    ]
    team = make_scored_team("t1", final_score=70.0, criteria_breakdowns=breakdowns)
    res = evaluate_ranking([team], top_x=1)
    sel = res.selected_teams[0]
    assert len(sel.criteria_breakdowns) == 2
    assert sel.criteria_breakdowns[0].criterion_id == "github_repos"
    assert sel.criteria_breakdowns[0].team_criterion_score == 0.9
    assert "Selected for Top-1 shortlist" in sel.explanation


def test_explanations_excluded_teams_have_reason_codes():
    """Case 22: Excluded teams have standardized reason codes and human explanations."""
    teams = [
        make_scored_team("t_inelig", final_score=70.0, eligibility_status=EligibilityStatus.INELIGIBLE, eligibility_summary="Under minimum CGPA"),
        make_scored_team("t_no_score", final_score=None, score_status=ScoreStatus.NO_SCORE),
        make_scored_team("temp_team_dup_unresolved_1", final_score=80.0),
    ]
    res = evaluate_ranking(teams, top_x=1)
    assert len(res.excluded_teams) == 3
    reasons = {e.team_id: e.reason_code for e in res.excluded_teams}
    assert reasons["t_inelig"] == ExclusionReason.INELIGIBLE
    assert reasons["t_no_score"] == ExclusionReason.NO_SCORE
    assert reasons["temp_team_dup_unresolved_1"] == ExclusionReason.UNRESOLVED


def test_explanations_completeness_information_preserved():
    """Case 23: Completeness and renormalization metrics are preserved in ranking results."""
    team = make_scored_team(
        "t1",
        final_score=60.0,
        weight_renormalized=True,
        applicable_weight=75.0,
    )
    res = evaluate_ranking([team], top_x=1)
    sel = res.selected_teams[0]
    assert sel.weight_renormalized is True
    assert sel.applicable_weight == 75.0
    assert sel.total_configured_weight == 100.0


def test_explanations_insufficient_candidate_warnings():
    """Case 24: Correct warning when candidate pool is smaller than requested top_x."""
    teams = [make_scored_team("t1", final_score=90.0)]
    res = evaluate_ranking(teams, top_x=5)
    assert any("shortage of 4" in w for w in res.warnings)


def test_explanations_review_recommendations_do_not_automatically_approve():
    """Case 25: Recommended review candidates are recommendations only; not approved into shortlist."""
    teams = [
        make_scored_team("t_elig", final_score=90.0, eligibility_status=EligibilityStatus.ELIGIBLE),
        make_scored_team("t_rev_1", final_score=88.0, eligibility_status=EligibilityStatus.NEEDS_REVIEW),
        make_scored_team("t_rev_2", final_score=85.0, eligibility_status=EligibilityStatus.NEEDS_REVIEW),
    ]
    res = evaluate_ranking(teams, top_x=3)  # shortage of 2
    # Shortlist must only contain 1 team
    assert len(res.selected_teams) == 1
    assert res.selected_teams[0].team_id == "t_elig"

    # Up to 2 highest review candidates are recommended
    assert len(res.recommended_review_candidates) == 2
    assert res.recommended_review_candidates[0].team_id == "t_rev_1"
    assert res.recommended_review_candidates[0].eligibility_status == EligibilityStatus.NEEDS_REVIEW
    assert res.recommended_review_candidates[0].selection_status == SelectionStatus.NEEDS_REVIEW


# ===========================================================================
# 5. INTEGRATION, PERSISTENCE, & API (Cases 26-30)
# ===========================================================================


def test_integration_existing_pipeline_compatibility():
    """Case 26: Full pipeline from ingestion -> signals -> rules -> scoring -> ranking works end-to-end."""
    csv_content = (
        "team_name,name,email,github_url,cgpa\n"
        "Alpha,Alice,alice@test.com,https://github.com/alice,9.0\n"
        "Beta,Bob,bob@test.com,https://github.com/bob,7.5\n"
        "Gamma,Charlie,charlie@test.com,https://github.com/charlie,6.0\n"
    )
    # Ingestion
    up = client.post("/api/ingestion/upload", files={"file": ("teams.csv", csv_content.encode("utf-8"), "text/csv")}).json()
    teams = up["teams"]
    # Signals
    ext = client.post("/api/signals/extract", json={"teams": teams, "selected_signals": ["academic_cgpa"]}).json()
    flat = client.post("/api/signals/flatten", json=ext).json()
    # Rules
    elig = client.post("/api/rules/evaluate", json={"teams": teams, "signals": flat, "config_id": "open_solo"}).json()
    elig_id = elig["run_id"]
    # Scoring
    score = client.post("/api/scoring/evaluate", json={"teams": teams, "signals": flat, "config_id": "balanced", "eligibility_run_id": elig_id}).json()
    score_id = score["run_id"]

    # Ranking via API referencing scoring_run_id
    rank_resp = client.post(
        "/api/ranking/evaluate",
        json={
            "top_x": 2,
            "scoring_run_id": score_id,
        },
    )
    assert rank_resp.status_code == 200, rank_resp.text
    rank_data = rank_resp.json()
    assert len(rank_data["selected_teams"]) == 2
    assert rank_data["summary"]["requested_top_x"] == 2
    assert rank_data["summary"]["selected_teams_count"] == 2


def test_integration_manual_override_respected_in_ranking():
    """Case 27: Manual overrides in eligibility run flow through scoring into ranking."""
    team_data = {
        "team_id": "t_override",
        "team_name": "Team Overridden",
        "members": [{"member_id": "m1", "name": "Eve", "email": "eve@test.com"}],
    }
    elig = client.post("/api/rules/evaluate", json={"teams": [team_data], "config_id": "open_solo"}).json()
    elig_id = elig["run_id"]

    # Apply override to disqualify team
    client.post(
        f"/api/rules/runs/{elig_id}/teams/t_override/override",
        json={"override_status": "INELIGIBLE", "reason": "Disqualified by organizer committee"},
    )

    # Score with eligibility_run_id and signals so team has a valid calculated score
    score = client.post(
        "/api/scoring/evaluate",
        json={
            "teams": [team_data],
            "signals": [
                {
                    "member_id": "m1",
                    "signals": [
                        {
                            "signal_key": "academic_cgpa",
                            "category": "academic",
                            "value": 8.5,
                            "status": "extracted",
                        }
                    ],
                }
            ],
            "config_id": "balanced",
            "eligibility_run_id": elig_id,
        },
    ).json()

    # Rank
    rank_res = client.post(
        "/api/ranking/evaluate",
        json={"top_x": 1, "scoring_run_id": score["run_id"]},
    ).json()

    assert len(rank_res["selected_teams"]) == 0
    assert len(rank_res["excluded_teams"]) == 1
    assert rank_res["excluded_teams"][0]["reason_code"] == "INELIGIBLE"
    assert "Disqualified by organizer committee" in rank_res["excluded_teams"][0]["explanation"]


def test_integration_api_run_retrieval_and_listing():
    """Case 28: Stored ranking runs can be queried by run_id and listed."""
    teams = [make_scored_team("t1", final_score=85.0)]
    resp = client.post(
        "/api/ranking/evaluate",
        json={"top_x": 1, "scoring_results": [teams[0].model_dump()]},
    )
    assert resp.status_code == 200
    run_id = resp.json()["run_id"]

    # GET run by ID
    get_resp = client.get(f"/api/ranking/runs/{run_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["run_id"] == run_id

    # Non-existent run
    assert client.get("/api/ranking/runs/nonexistent_123").status_code == 404

    # List runs
    list_resp = client.get("/api/ranking/runs")
    assert list_resp.status_code == 200
    assert any(r["run_id"] == run_id for r in list_resp.json())


def test_integration_ranking_uses_existing_scoring_results():
    """Case 29: Ranking uses existing scoring results without re-evaluating or modifying them."""
    breakdown = make_breakdown("custom_sig", team_criterion_score=0.95, weighted_contribution=40.0)
    team = make_scored_team("t_precomputed", final_score=92.34, criteria_breakdowns=[breakdown])

    rank_res = evaluate_ranking([team], top_x=1)
    sel = rank_res.selected_teams[0]
    assert sel.final_score == 92.34
    assert sel.criteria_breakdowns[0].team_criterion_score == 0.95


def test_integration_run_parameters_and_traceability_retained():
    """Case 30: Run parameters (top_x, tiebreak_criterion_id, include_needs_review, timestamps) are fully retained."""
    team = make_scored_team("t1", final_score=88.0)
    rank_res = evaluate_ranking(
        [team],
        top_x=5,
        tiebreak_criterion_id="crit_alpha",
        include_needs_review=True,
        scoring_run_id="score_run_123",
        eligibility_run_id="elig_run_456",
        run_id="rank_custom_id_789",
        evaluated_at="2026-10-16T12:00:00Z",
    )
    assert rank_res.run_id == "rank_custom_id_789"
    assert rank_res.scoring_run_id == "score_run_123"
    assert rank_res.eligibility_run_id == "elig_run_456"
    assert rank_res.evaluated_at == "2026-10-16T12:00:00Z"
    assert rank_res.top_x == 5
    assert rank_res.include_needs_review is True
    assert rank_res.tiebreak_criterion_id == "crit_alpha"


# ---------------------------------------------------------------------------
# Phase 6.1: Integration Fixes & Regression Verification Tests
# ---------------------------------------------------------------------------


def test_fix1_ranking_uses_effective_eligibility_status_and_overrides():
    """Phase 6.1 FIX 1: Ranking uses effective eligibility status with overrides in both directions."""
    teams = [
        {
            "team_id": "T_A",
            "team_name": "Team A",
            "members": [
                {"member_id": "m1", "name": "Alice", "github_url": "https://github.com/alice"},
                {"member_id": "m2", "name": "Aaron", "github_url": "https://github.com/aaron"},
            ],
        },
        {
            "team_id": "T_B",
            "team_name": "Team B",
            "members": [
                {"member_id": "m3", "name": "Bob", "github_url": "https://github.com/bob"},
                {"member_id": "m4", "name": "Bella", "github_url": "https://github.com/bella"},
            ],
        },
    ]
    signals_elig = [
        {
            "member_id": "m1",
            "signals": [
                {"signal_key": "academic_cgpa", "category": "academic", "value": 8.5, "status": "extracted"},
                {"signal_key": "github_public_repo_count", "category": "github", "value": 3, "status": "extracted"},
            ],
        },
        {
            "member_id": "m2",
            "signals": [
                {"signal_key": "academic_cgpa", "category": "academic", "value": 8.0, "status": "extracted"},
                {"signal_key": "github_public_repo_count", "category": "github", "value": 2, "status": "extracted"},
            ],
        },
    ]

    # Evaluate rules under strict preset: T_A is ELIGIBLE, T_B is NEEDS_REVIEW (CGPA missing)
    res_elig = client.post(
        "/api/rules/evaluate",
        json={"teams": teams, "signals": signals_elig, "config_id": "strict"},
    ).json()
    elig_id = res_elig["run_id"]
    assert next(t["status"] for t in res_elig["teams"] if t["team_id"] == "T_A") == "ELIGIBLE"
    assert next(t["status"] for t in res_elig["teams"] if t["team_id"] == "T_B") == "NEEDS_REVIEW"

    # Score teams under balanced preset (provide signals for all members so both teams have calculated scores)
    signals_score = signals_elig + [
        {"member_id": "m3", "signals": [{"signal_key": "academic_cgpa", "category": "academic", "value": 9.0, "status": "extracted"}]},
        {"member_id": "m4", "signals": [{"signal_key": "academic_cgpa", "category": "academic", "value": 9.0, "status": "extracted"}]},
    ]
    score_res = client.post(
        "/api/scoring/evaluate",
        json={
            "teams": teams,
            "signals": signals_score,
            "config_id": "balanced",
            "eligibility_run_id": elig_id,
        },
    ).json()
    score_id = score_res["run_id"]

    # Verify initial scoring record in store has T_A ELIGIBLE and T_B NEEDS_REVIEW
    stored_score_before = default_scoring_run_store.get(score_id)
    assert stored_score_before is not None
    assert next(t.eligibility_status for t in stored_score_before.teams if t.team_id == "T_A") == EligibilityStatus.ELIGIBLE
    assert next(t.eligibility_status for t in stored_score_before.teams if t.team_id == "T_B") == EligibilityStatus.NEEDS_REVIEW

    # Apply manual overrides in BOTH directions:
    # 1. T_A: ELIGIBLE -> INELIGIBLE (excludes candidate)
    ovr_a = client.post(
        f"/api/rules/runs/{elig_id}/teams/T_A/override",
        json={"override_status": "INELIGIBLE", "reason": "Disqualified post-scoring by organizer committee"},
    )
    assert ovr_a.status_code == 200

    # 2. T_B: NEEDS_REVIEW -> ELIGIBLE (selects candidate)
    ovr_b = client.post(
        f"/api/rules/runs/{elig_id}/teams/T_B/override",
        json={"override_status": "ELIGIBLE", "reason": "Academic transcripts verified offline"},
    )
    assert ovr_b.status_code == 200

    # Rank with scoring_run_id + eligibility_run_id
    rank_res = client.post(
        "/api/ranking/evaluate",
        json={"top_x": 2, "scoring_run_id": score_id, "eligibility_run_id": elig_id},
    )
    assert rank_res.status_code == 200
    rank_data = rank_res.json()

    # Assert overridden status is used in both directions:
    # T_A (overridden to INELIGIBLE) is excluded
    assert len(rank_data["selected_teams"]) == 1
    assert rank_data["selected_teams"][0]["team_id"] == "T_B"
    assert rank_data["selected_teams"][0]["selection_status"] == SelectionStatus.SELECTED

    # T_A is in excluded_teams with reason_code INELIGIBLE and explanation containing override reason
    assert len(rank_data["excluded_teams"]) == 1
    excl_a = rank_data["excluded_teams"][0]
    assert excl_a["team_id"] == "T_A"
    assert excl_a["reason_code"] == ExclusionReason.INELIGIBLE
    assert "Disqualified post-scoring by organizer committee" in excl_a["explanation"]

    # Assert stored scoring run is NOT mutated
    stored_score_after = default_scoring_run_store.get(score_id)
    assert stored_score_after is not None
    assert next(t.eligibility_status for t in stored_score_after.teams if t.team_id == "T_A") == EligibilityStatus.ELIGIBLE
    assert next(t.eligibility_status for t in stored_score_after.teams if t.team_id == "T_B") == EligibilityStatus.NEEDS_REVIEW

    # Missing eligibility_run_id returns HTTP 404
    resp_404 = client.post(
        "/api/ranking/evaluate",
        json={"top_x": 1, "scoring_run_id": score_id, "eligibility_run_id": "nonexistent_elig_id_999"},
    )
    assert resp_404.status_code == 404

    # Unmatched team in eligibility run leaves status as-is and adds warning
    unmatched_team = make_scored_team("T_UNMATCHED", final_score=80.0, eligibility_status=EligibilityStatus.ELIGIBLE)
    res_unmatched = evaluate_ranking([unmatched_team], top_x=1, eligibility_run_id=elig_id)
    assert res_unmatched.selected_teams[0].team_id == "T_UNMATCHED"
    assert res_unmatched.selected_teams[0].eligibility_status == EligibilityStatus.ELIGIBLE
    assert any("Team 'T_UNMATCHED' was not found in eligibility run" in w for w in res_unmatched.warnings)


def test_fix2_balanced_preset_no_signals_yields_no_score():
    """Phase 6.1 FIX 2: Team with no extracted signals scored with 'balanced' gets NO_SCORE and is excluded by ranking."""
    team_data = {
        "team_id": "t_no_signals",
        "team_name": "Team Zero Signal",
        "members": [{"member_id": "m1", "name": "Member One", "email": "m1@example.com"}],
    }

    # Score with balanced preset without extracting signals
    score_resp = client.post(
        "/api/scoring/evaluate",
        json={"teams": [team_data], "config_id": "balanced"},
    )
    assert score_resp.status_code == 200
    score_body = score_resp.json()
    team_res = score_body["teams"][0]
    assert team_res["score_status"] == ScoreStatus.NO_SCORE
    assert team_res["final_score"] is None

    # Ranking must exclude this team with reason code NO_SCORE
    rank_resp = client.post(
        "/api/ranking/evaluate",
        json={"top_x": 1, "scoring_run_id": score_body["run_id"]},
    )
    assert rank_resp.status_code == 200
    rank_body = rank_resp.json()
    assert len(rank_body["selected_teams"]) == 0
    assert len(rank_body["excluded_teams"]) == 1
    excl = rank_body["excluded_teams"][0]
    assert excl["team_id"] == "t_no_signals"
    assert excl["reason_code"] == ExclusionReason.NO_SCORE


def test_fix3_ranking_duplicate_team_id_and_boolean_top_x():
    """Phase 6.1 FIX 3: Deduplicate duplicate team_id with warning, and reject boolean top_x."""
    # 1. Deduplicate team_id in scoring_results
    t_dup_1 = make_scored_team("T_DUP", final_score=90.0, team_name="First T_DUP")
    t_dup_2 = make_scored_team("T_DUP", final_score=50.0, team_name="Second T_DUP")
    t_other = make_scored_team("T_OTHER", final_score=80.0, team_name="Other Team")

    res = evaluate_ranking([t_dup_1, t_dup_2, t_other], top_x=2)
    assert len(res.selected_teams) == 2
    assert res.selected_teams[0].team_id == "T_DUP"
    assert res.selected_teams[0].final_score == 90.0
    assert res.selected_teams[1].team_id == "T_OTHER"
    assert any("Duplicate team_id 'T_DUP'" in w for w in res.warnings)

    # 2. Schema rejection of boolean top_x (HTTP 422)
    api_resp = client.post(
        "/api/ranking/evaluate",
        json={"top_x": True, "scoring_results": [t_other.model_dump()]},
    )
    assert api_resp.status_code == 422

    # 3. Engine rejection of boolean top_x (ValueError)
    with pytest.raises(ValueError, match="top_x must be a positive integer"):
        evaluate_ranking([t_other], top_x=True)  # type: ignore[arg-type]
