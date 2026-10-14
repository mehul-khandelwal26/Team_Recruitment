"""Comprehensive test suite for Phase 5 Weighted Scoring and Team Aggregation.

Covers:
- A. Weights (sum to 1, 100, relative 2/3/5, disabled criteria, negative/nan/zero validation)
- B. Normalization (min-max linear, out of bounds, bounds validation, boolean, categorical, zero preservation, numeric safety)
- C. Aggregation (mean, min, max, sum with clamped bounds, lead_only, top_k, variable team sizes, empty teams)
- D. Missing Data (all SignalStatuses, absent signals, genuine zero, EXCLUDE_AND_RENORMALIZE, ZERO_SCORE, no usable criteria)
- E. Eligibility Integration (ELIGIBLE, INELIGIBLE, NEEDS_REVIEW, no eligibility supplied, status immutability)
- F. Explanations & Determinism (contribution reconciliation, deterministic sorting, fault isolation)
- G. Configuration & API (creation, retrieval, immutability, version history, HTTP 422 validations, run persistence)
"""

from __future__ import annotations

import math
from typing import Any
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.rules.schemas import EligibilityStatus
from app.schemas.ingestion import MemberSchema, TeamSchema
from app.scoring.config_store import default_scoring_config_store
from app.scoring.engine import (
    calculate_team_score,
    evaluate_scoring,
    normalize_value,
    parse_numeric_safely,
)
from app.scoring.schemas import (
    AggregationMethod,
    BooleanMappingConfig,
    CategoricalMappingConfig,
    CriterionType,
    EvaluationCriterion,
    LinearRangeConfig,
    MissingDataPolicy,
    NormalizationConfig,
    ScoreStatus,
    ScoringConfiguration,
)
from app.scoring.store import default_scoring_run_store
from app.scoring.validation import validate_scoring_configuration, validate_scoring_criterion
from app.signals.schemas import ExtractedSignal, SignalEvidence, SignalStatus

client = TestClient(app)


# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_scoring_stores():
    """Ensure clean store state before every test."""
    default_scoring_config_store.reset()
    default_scoring_run_store.reset()
    yield
    default_scoring_config_store.reset()
    default_scoring_run_store.reset()


def make_member(
    member_id: str,
    name: str = "Alice",
    custom_fields: dict[str, Any] | None = None,
    raw_data: dict[str, Any] | None = None,
    **kwargs: Any,
) -> MemberSchema:
    return MemberSchema(
        member_id=member_id,
        name=name,
        custom_fields=custom_fields or {},
        raw_data=raw_data or {},
        **kwargs,
    )


def make_team(team_id: str, team_name: str, members: list[MemberSchema]) -> TeamSchema:
    return TeamSchema(team_id=team_id, team_name=team_name, members=members)


def make_signal(
    signal_key: str,
    value: Any,
    status: SignalStatus = SignalStatus.EXTRACTED,
    confidence: float | None = 1.0,
    source: str = "test",
) -> ExtractedSignal:
    return ExtractedSignal(
        signal_key=signal_key,
        category="test",
        value=value,
        status=status,
        evidence=SignalEvidence(source=source, confidence=confidence),
    )


# ===========================================================================
# A. Weights & Relative Normalization Tests
# ===========================================================================


class TestWeightsAndRelativeNormalization:
    def test_weights_totaling_one(self):
        """Weights totaling 1.0 (0.4 and 0.6) are normalized and evaluated proportionally."""
        c1 = EvaluationCriterion(
            criterion_id="c1",
            name="C1",
            target_signal_key="github_public_repo_count",
            criterion_type=CriterionType.NUMERIC_RANGE,
            weight=0.4,
            normalization=NormalizationConfig(linear_range=LinearRangeConfig(min_value=0.0, max_value=10.0)),
        )
        c2 = EvaluationCriterion(
            criterion_id="c2",
            name="C2",
            target_signal_key="academic_cgpa",
            criterion_type=CriterionType.NUMERIC_RANGE,
            weight=0.6,
            normalization=NormalizationConfig(linear_range=LinearRangeConfig(min_value=0.0, max_value=10.0)),
        )
        cfg = ScoringConfiguration(config_id="w1", name="W1", criteria=[c1, c2], scale_max=100.0)

        # Team member has 10 repos (score=1.0) and 5 CGPA (score=0.5)
        m = make_member("m1")
        sigs = {
            "m1": {
                "github_public_repo_count": make_signal("github_public_repo_count", 10),
                "academic_cgpa": make_signal("academic_cgpa", 5.0),
            }
        }
        res = calculate_team_score(make_team("t1", "T1", [m]), cfg, sigs)

        assert res.score_status == ScoreStatus.CALCULATED
        # c1 contribution = 1.0 * 0.4 * 100 = 40.0
        # c2 contribution = 0.5 * 0.6 * 100 = 30.0
        # Total = 70.0
        assert res.final_score == 70.0
        assert res.criteria_breakdowns[0].weighted_contribution == 40.0
        assert res.criteria_breakdowns[1].weighted_contribution == 30.0

    def test_weights_totaling_hundred(self):
        """Weights totaling 100 (40 and 60) produce identical proportional normalized weights."""
        c1 = EvaluationCriterion(
            criterion_id="c1",
            name="C1",
            target_signal_key="github_public_repo_count",
            criterion_type=CriterionType.NUMERIC_RANGE,
            weight=40.0,
            normalization=NormalizationConfig(linear_range=LinearRangeConfig(min_value=0.0, max_value=10.0)),
        )
        c2 = EvaluationCriterion(
            criterion_id="c2",
            name="C2",
            target_signal_key="academic_cgpa",
            criterion_type=CriterionType.NUMERIC_RANGE,
            weight=60.0,
            normalization=NormalizationConfig(linear_range=LinearRangeConfig(min_value=0.0, max_value=10.0)),
        )
        cfg = ScoringConfiguration(config_id="w100", name="W100", criteria=[c1, c2], scale_max=100.0)

        m = make_member("m1")
        sigs = {
            "m1": {
                "github_public_repo_count": make_signal("github_public_repo_count", 10),
                "academic_cgpa": make_signal("academic_cgpa", 5.0),
            }
        }
        res = calculate_team_score(make_team("t1", "T1", [m]), cfg, sigs)
        assert res.final_score == 70.0

    def test_arbitrary_relative_weights(self):
        """Weights 2, 3, and 5 normalize to 0.2, 0.3, and 0.5."""
        c1 = EvaluationCriterion(
            criterion_id="c1",
            name="C1",
            target_signal_key="github_public_repo_count",
            criterion_type=CriterionType.NUMERIC_RANGE,
            weight=2.0,
            normalization=NormalizationConfig(linear_range=LinearRangeConfig(min_value=0.0, max_value=10.0)),
        )
        c2 = EvaluationCriterion(
            criterion_id="c2",
            name="C2",
            target_signal_key="academic_cgpa",
            criterion_type=CriterionType.NUMERIC_RANGE,
            weight=3.0,
            normalization=NormalizationConfig(linear_range=LinearRangeConfig(min_value=0.0, max_value=10.0)),
        )
        c3 = EvaluationCriterion(
            criterion_id="c3",
            name="C3",
            target_signal_key="resume_experience_years",
            criterion_type=CriterionType.NUMERIC_RANGE,
            weight=5.0,
            normalization=NormalizationConfig(linear_range=LinearRangeConfig(min_value=0.0, max_value=10.0)),
        )
        cfg = ScoringConfiguration(config_id="w_rel", name="W_Rel", criteria=[c1, c2, c3], scale_max=100.0)

        m = make_member("m1")
        sigs = {
            "m1": {
                "github_public_repo_count": make_signal("github_public_repo_count", 10),  # 1.0 * 0.2 * 100 = 20
                "academic_cgpa": make_signal("academic_cgpa", 10),                        # 1.0 * 0.3 * 100 = 30
                "resume_experience_years": make_signal("resume_experience_years", 10),     # 1.0 * 0.5 * 100 = 50
            }
        }
        res = calculate_team_score(make_team("t1", "T1", [m]), cfg, sigs)
        assert res.final_score == 100.0
        assert res.criteria_breakdowns[0].normalized_weight == 0.2
        assert res.criteria_breakdowns[1].normalized_weight == 0.3
        assert res.criteria_breakdowns[2].normalized_weight == 0.5

    def test_disabled_criteria_do_not_contribute(self):
        """Disabled criteria (is_enabled=False) do not contribute to score or weight totals."""
        c1 = EvaluationCriterion(
            criterion_id="c1",
            name="C1",
            target_signal_key="github_public_repo_count",
            criterion_type=CriterionType.NUMERIC_RANGE,
            weight=50.0,
            is_enabled=True,
            normalization=NormalizationConfig(linear_range=LinearRangeConfig(min_value=0.0, max_value=10.0)),
        )
        c2 = EvaluationCriterion(
            criterion_id="c2",
            name="C2",
            target_signal_key="academic_cgpa",
            criterion_type=CriterionType.NUMERIC_RANGE,
            weight=50.0,
            is_enabled=False,  # Disabled
            normalization=NormalizationConfig(linear_range=LinearRangeConfig(min_value=0.0, max_value=10.0)),
        )
        cfg = ScoringConfiguration(config_id="cfg_dis", name="Cfg Dis", criteria=[c1, c2])

        m = make_member("m1")
        sigs = {
            "m1": {
                "github_public_repo_count": make_signal("github_public_repo_count", 5),
                "academic_cgpa": make_signal("academic_cgpa", 10),
            }
        }
        res = calculate_team_score(make_team("t1", "T1", [m]), cfg, sigs)
        assert len(res.criteria_breakdowns) == 1
        assert res.criteria_breakdowns[0].criterion_id == "c1"
        assert res.criteria_breakdowns[0].normalized_weight == 1.0
        assert res.final_score == 50.0

    def test_validation_rejects_negative_nan_and_zero_total_weight(self):
        """Validation rejects negative weights, non-finite weights, and all-zero enabled weights."""
        with pytest.raises(Exception):
            EvaluationCriterion(
                criterion_id="c_neg",
                name="Neg",
                target_signal_key="github_public_repo_count",
                criterion_type=CriterionType.NUMERIC_RANGE,
                weight=-5.0,
                normalization=NormalizationConfig(linear_range=LinearRangeConfig(min_value=0.0, max_value=10.0)),
            )

        # All-zero enabled weights
        c_zero = EvaluationCriterion(
            criterion_id="c_zero",
            name="Zero",
            target_signal_key="github_public_repo_count",
            criterion_type=CriterionType.NUMERIC_RANGE,
            weight=0.0,
            normalization=NormalizationConfig(linear_range=LinearRangeConfig(min_value=0.0, max_value=10.0)),
        )
        cfg_zero = ScoringConfiguration(config_id="z", name="Z", criteria=[c_zero])
        cfg_errs = validate_scoring_configuration(cfg_zero)
        assert any("greater than 0" in e for e in cfg_errs)


# ===========================================================================
# B. Normalization & Numeric Safety Tests
# ===========================================================================


class TestNormalizationAndNumericSafety:
    def test_min_max_linear_mapping_and_clamping(self):
        """Linear mapping clamps out-of-range values and scales in-between values accurately."""
        crit = EvaluationCriterion(
            criterion_id="c",
            name="C",
            target_signal_key="github_public_repo_count",
            criterion_type=CriterionType.NUMERIC_RANGE,
            normalization=NormalizationConfig(linear_range=LinearRangeConfig(min_value=10.0, max_value=20.0)),
        )
        # Below min (5) -> clamped to 0.0
        s_low, _ = normalize_value(5, crit)
        assert s_low == 0.0

        # Exact min (10) -> 0.0
        s_min, _ = normalize_value(10, crit)
        assert s_min == 0.0

        # Intermediate (15) -> 0.5
        s_mid, _ = normalize_value(15, crit)
        assert s_mid == 0.5

        # Exact max (20) -> 1.0
        s_max, _ = normalize_value(20, crit)
        assert s_max == 1.0

        # Above max (50) -> clamped to 1.0
        s_high, _ = normalize_value(50, crit)
        assert s_high == 1.0

    def test_genuine_numeric_zero_preserved(self):
        """Genuine numeric zero (0, 0.0) is valid and scales properly."""
        crit = EvaluationCriterion(
            criterion_id="c",
            name="C",
            target_signal_key="github_public_repo_count",
            criterion_type=CriterionType.NUMERIC_RANGE,
            normalization=NormalizationConfig(linear_range=LinearRangeConfig(min_value=0.0, max_value=10.0)),
        )
        s_zero, exp = normalize_value(0, crit)
        assert s_zero == 0.0
        assert "0.0" in exp

        s_zero_f, _ = normalize_value(0.0, crit)
        assert s_zero_f == 0.0

    def test_invalid_normalization_bounds_rejected(self):
        """Validation rejects max_value <= min_value."""
        with pytest.raises(ValueError):
            LinearRangeConfig(min_value=10.0, max_value=5.0)

        with pytest.raises(ValueError):
            LinearRangeConfig(min_value=10.0, max_value=10.0)

    def test_numeric_safety_rejects_bool_nan_and_inf(self):
        """Booleans (True/False), NaN, and Infinity are rejected as invalid numeric data."""
        # True is not 1
        num, ok = parse_numeric_safely(True)
        assert ok is False and num is None

        # False is not 0
        num, ok = parse_numeric_safely(False)
        assert ok is False and num is None

        # NaN
        num, ok = parse_numeric_safely(float("nan"))
        assert ok is False and num is None

        # Inf
        num, ok = parse_numeric_safely(float("inf"))
        assert ok is False and num is None

    def test_boolean_mapping(self):
        """Boolean mapping maps True and False to configured scores."""
        crit = EvaluationCriterion(
            criterion_id="c_bool",
            name="Verified",
            target_signal_key="github_profile_verified",
            criterion_type=CriterionType.BOOLEAN,
            normalization=NormalizationConfig(boolean_mapping=BooleanMappingConfig(true_score=1.0, false_score=0.2)),
        )
        s_true, _ = normalize_value(True, crit)
        assert s_true == 1.0

        s_false, _ = normalize_value(False, crit)
        assert s_false == 0.2

    def test_categorical_mapping_and_unknown_handling(self):
        """Categorical mapping looks up allowed categories and applies default or unmapped policy."""
        crit = EvaluationCriterion(
            criterion_id="c_cat",
            name="Year",
            target_signal_key="academic_year",
            criterion_type=CriterionType.CATEGORICAL,
            normalization=NormalizationConfig(
                categorical_mapping=CategoricalMappingConfig(
                    category_scores={"3rd Year": 0.75, "4th Year": 1.0},
                    default_score=0.5,
                    case_sensitive=False,
                )
            ),
        )
        s_match, _ = normalize_value("3rd year", crit)
        assert s_match == 0.75

        s_def, _ = normalize_value("Freshman", crit)
        assert s_def == 0.5


# ===========================================================================
# C. Member-to-Team Aggregation Tests
# ===========================================================================


class TestMemberToTeamAggregation:
    def test_all_aggregation_methods(self):
        """Test mean, min, max, and sum on a 3-member team with scores 0.2, 0.4, 0.8."""
        m1 = make_member("m1")
        m2 = make_member("m2")
        m3 = make_member("m3")
        team = make_team("t1", "T1", [m1, m2, m3])

        # Scores 2, 4, 8 out of 10 -> normalized 0.2, 0.4, 0.8
        sigs = {
            "m1": {"github_public_repo_count": make_signal("github_public_repo_count", 2)},
            "m2": {"github_public_repo_count": make_signal("github_public_repo_count", 4)},
            "m3": {"github_public_repo_count": make_signal("github_public_repo_count", 8)},
        }

        def eval_with_agg(method, top_k=None):
            crit = EvaluationCriterion(
                criterion_id="c",
                name="C",
                target_signal_key="github_public_repo_count",
                criterion_type=CriterionType.NUMERIC_RANGE,
                weight=1.0,
                aggregation=method,
                top_k_value=top_k,
                normalization=NormalizationConfig(linear_range=LinearRangeConfig(min_value=0.0, max_value=10.0)),
            )
            cfg = ScoringConfiguration(config_id="c", name="C", criteria=[crit])
            return calculate_team_score(team, cfg, sigs)

        # MEAN: (0.2 + 0.4 + 0.8) / 3 = 1.4 / 3 ≈ 0.4667 -> * 100 = 46.67
        res_mean = eval_with_agg(AggregationMethod.MEAN)
        assert res_mean.final_score == pytest.approx(46.67, 0.01)

        # MIN: min(0.2, 0.4, 0.8) = 0.2 -> * 100 = 20.0
        res_min = eval_with_agg(AggregationMethod.MIN)
        assert res_min.final_score == 20.0

        # MAX: max(0.2, 0.4, 0.8) = 0.8 -> * 100 = 80.0
        res_max = eval_with_agg(AggregationMethod.MAX)
        assert res_max.final_score == 80.0

        # SUM (clamped): 0.2 + 0.4 + 0.8 = 1.4 -> clamped to 1.0 -> * 100 = 100.0
        res_sum = eval_with_agg(AggregationMethod.SUM)
        assert res_sum.final_score == 100.0

        # TOP_K (K=2): (0.8 + 0.4) / 2 = 0.6 -> * 100 = 60.0
        res_top2 = eval_with_agg(AggregationMethod.TOP_K, top_k=2)
        assert res_top2.final_score == 60.0

    def test_lead_only_aggregation(self):
        """Lead-only aggregation uses designated team lead's score."""
        m1 = make_member("m1", name="Dev Alice", custom_fields={"role": "Contributor"})
        m2 = make_member("m2", name="Lead Bob", custom_fields={"role": "Team Lead"})
        team = make_team("t1", "T1", [m1, m2])

        sigs = {
            "m1": {"github_public_repo_count": make_signal("github_public_repo_count", 2)},  # 0.2
            "m2": {"github_public_repo_count": make_signal("github_public_repo_count", 9)},  # 0.9
        }
        crit = EvaluationCriterion(
            criterion_id="c",
            name="C",
            target_signal_key="github_public_repo_count",
            criterion_type=CriterionType.NUMERIC_RANGE,
            weight=1.0,
            aggregation=AggregationMethod.LEAD_ONLY,
            normalization=NormalizationConfig(linear_range=LinearRangeConfig(min_value=0.0, max_value=10.0)),
        )
        cfg = ScoringConfiguration(config_id="c", name="C", criteria=[crit], lead_field="role")
        res = calculate_team_score(team, cfg, sigs)
        # Should evaluate Bob (0.9 * 100 = 90.0)
        assert res.final_score == 90.0

    def test_unidentified_team_lead_triggers_missing_policy(self):
        """If designated lead cannot be found, criterion treats score as missing."""
        m1 = make_member("m1", custom_fields={"role": "Member"})
        team = make_team("t1", "T1", [m1])
        sigs = {"m1": {"github_public_repo_count": make_signal("github_public_repo_count", 5)}}

        crit = EvaluationCriterion(
            criterion_id="c",
            name="C",
            target_signal_key="github_public_repo_count",
            criterion_type=CriterionType.NUMERIC_RANGE,
            weight=1.0,
            aggregation=AggregationMethod.LEAD_ONLY,
            missing_data_policy=MissingDataPolicy.ZERO_SCORE,
            normalization=NormalizationConfig(linear_range=LinearRangeConfig(min_value=0.0, max_value=10.0)),
        )
        cfg = ScoringConfiguration(config_id="c", name="C", criteria=[crit], lead_field="role")
        res = calculate_team_score(team, cfg, sigs)
        assert res.final_score == 0.0

    def test_empty_team_returns_no_score(self):
        """Team with zero members returns NO_SCORE via fault-tolerant parsing."""
        team_dict = {"team_id": "t_empty", "team_name": "Empty", "members": []}
        cfg = default_scoring_config_store.get("balanced")
        run = evaluate_scoring(teams=[team_dict], signals=None, config=cfg)
        assert run.teams[0].score_status == ScoreStatus.NO_SCORE
        assert run.teams[0].final_score is None


# ===========================================================================
# D. Missing-Data Handling Tests
# ===========================================================================


class TestMissingDataPolicies:
    def test_exclude_and_renormalize_policy(self):
        """EXCLUDE_AND_RENORMALIZE drops missing criterion and renormalizes remaining weights."""
        c1 = EvaluationCriterion(
            criterion_id="c1",
            name="C1",
            target_signal_key="github_public_repo_count",
            criterion_type=CriterionType.NUMERIC_RANGE,
            weight=50.0,
            missing_data_policy=MissingDataPolicy.EXCLUDE_AND_RENORMALIZE,
            normalization=NormalizationConfig(linear_range=LinearRangeConfig(min_value=0.0, max_value=10.0)),
        )
        c2 = EvaluationCriterion(
            criterion_id="c2",
            name="C2",
            target_signal_key="academic_cgpa",
            criterion_type=CriterionType.NUMERIC_RANGE,
            weight=50.0,
            missing_data_policy=MissingDataPolicy.EXCLUDE_AND_RENORMALIZE,
            normalization=NormalizationConfig(linear_range=LinearRangeConfig(min_value=0.0, max_value=10.0)),
        )
        cfg = ScoringConfiguration(config_id="cfg", name="Cfg", criteria=[c1, c2])

        # Member only has c1 (repos=8/10 -> 0.8), c2 is absent
        m = make_member("m1")
        sigs = {"m1": {"github_public_repo_count": make_signal("github_public_repo_count", 8)}}

        res = calculate_team_score(make_team("t1", "T1", [m]), cfg, sigs)
        # c2 excluded -> c1 renormalized from 50/100 to 1.0 weight -> score = 0.8 * 1.0 * 100 = 80.0
        assert res.final_score == 80.0
        assert res.weight_renormalized is True
        assert res.applicable_weight == 50.0
        assert res.total_configured_weight == 100.0

    def test_zero_score_policy(self):
        """ZERO_SCORE retains full denominator weight and assigns 0.0 to missing criterion."""
        c1 = EvaluationCriterion(
            criterion_id="c1",
            name="C1",
            target_signal_key="github_public_repo_count",
            criterion_type=CriterionType.NUMERIC_RANGE,
            weight=50.0,
            normalization=NormalizationConfig(linear_range=LinearRangeConfig(min_value=0.0, max_value=10.0)),
        )
        c2 = EvaluationCriterion(
            criterion_id="c2",
            name="C2",
            target_signal_key="academic_cgpa",
            criterion_type=CriterionType.NUMERIC_RANGE,
            weight=50.0,
            missing_data_policy=MissingDataPolicy.ZERO_SCORE,
            normalization=NormalizationConfig(linear_range=LinearRangeConfig(min_value=0.0, max_value=10.0)),
        )
        cfg = ScoringConfiguration(config_id="cfg", name="Cfg", criteria=[c1, c2])

        m = make_member("m1")
        sigs = {"m1": {"github_public_repo_count": make_signal("github_public_repo_count", 8)}}  # c2 absent

        res = calculate_team_score(make_team("t1", "T1", [m]), cfg, sigs)
        # c1 contribution = 0.8 * 0.5 * 100 = 40.0
        # c2 contribution = 0.0 * 0.5 * 100 = 0.0
        # Total = 40.0
        assert res.final_score == 40.0
        assert res.weight_renormalized is False
        assert res.criteria_breakdowns[1].team_criterion_score == 0.0
        assert res.criteria_breakdowns[1].missing_data_applied is True

    def test_all_signals_missing_returns_no_score(self):
        """When all criteria are missing under EXCLUDE_AND_RENORMALIZE, returns NO_SCORE (not 0.0)."""
        c1 = EvaluationCriterion(
            criterion_id="c1",
            name="C1",
            target_signal_key="github_public_repo_count",
            criterion_type=CriterionType.NUMERIC_RANGE,
            weight=10.0,
            missing_data_policy=MissingDataPolicy.EXCLUDE_AND_RENORMALIZE,
            normalization=NormalizationConfig(linear_range=LinearRangeConfig(min_value=0.0, max_value=10.0)),
        )
        cfg = ScoringConfiguration(config_id="cfg", name="Cfg", criteria=[c1])
        m = make_member("m1")
        res = calculate_team_score(make_team("t1", "T1", [m]), cfg, {})
        assert res.score_status == ScoreStatus.NO_SCORE
        assert res.final_score is None

    @pytest.mark.parametrize("status", [
        SignalStatus.NOT_APPLICABLE,
        SignalStatus.FAILED,
        SignalStatus.PENDING,
        SignalStatus.SKIPPED,
    ])
    def test_all_non_extracted_signal_statuses_handled_safely(self, status):
        """NOT_APPLICABLE, FAILED, PENDING, and SKIPPED are treated as missing data."""
        crit = EvaluationCriterion(
            criterion_id="c",
            name="C",
            target_signal_key="github_public_repo_count",
            criterion_type=CriterionType.NUMERIC_RANGE,
            weight=1.0,
            missing_data_policy=MissingDataPolicy.ZERO_SCORE,
            normalization=NormalizationConfig(linear_range=LinearRangeConfig(min_value=0.0, max_value=10.0)),
        )
        cfg = ScoringConfiguration(config_id="cfg", name="Cfg", criteria=[crit])
        m = make_member("m1")
        sigs = {"m1": {"github_public_repo_count": make_signal("github_public_repo_count", None, status=status)}}
        res = calculate_team_score(make_team("t1", "T1", [m]), cfg, sigs)
        assert res.final_score == 0.0
        assert res.criteria_breakdowns[0].missing_data_applied is True


# ===========================================================================
# E. Eligibility Integration Tests
# ===========================================================================


class TestEligibilityIntegration:
    def test_eligible_team_score_calculated_and_status_preserved(self):
        """Eligible team calculates score and preserves ELIGIBLE status."""
        cfg = default_scoring_config_store.get("balanced")
        team = make_team("t1", "Alpha", [make_member("m1")])
        sigs = [
            {
                "member_id": "m1",
                "signals": [
                    {"signal_key": "github_public_repo_count", "category": "technical", "status": "extracted", "value": 10},
                    {"signal_key": "academic_cgpa", "category": "academic", "status": "extracted", "value": 8.0},
                ],
            }
        ]
        elig_results = [{"team_id": "t1", "status": "ELIGIBLE", "summary": "Passed all hard rules"}]

        run = evaluate_scoring(
            teams=[team],
            signals=sigs,
            config=cfg,
            eligibility_results=elig_results,
        )
        assert run.teams[0].eligibility_status == EligibilityStatus.ELIGIBLE
        assert run.teams[0].score_status == ScoreStatus.CALCULATED
        assert run.teams[0].final_score is not None

    def test_ineligible_team_preserves_ineligible_status(self):
        """Ineligible team preserves status without mutating it to ELIGIBLE."""
        cfg = default_scoring_config_store.get("balanced")
        team = make_team("t1", "Beta", [make_member("m1")])
        elig_results = [{"team_id": "t1", "status": "INELIGIBLE", "summary": "Team size too small"}]

        run = evaluate_scoring(
            teams=[team],
            signals=None,
            config=cfg,
            eligibility_results=elig_results,
        )
        assert run.teams[0].eligibility_status == EligibilityStatus.INELIGIBLE
        # Eligibility decision is intact

    def test_ineligible_team_disqualified_when_configured(self):
        """When score_ineligible_teams=False, ineligible team receives 0.0 and DISQUALIFIED."""
        cfg = default_scoring_config_store.get("balanced").model_copy(deep=True)
        cfg.score_ineligible_teams = False

        team = make_team("t1", "Beta", [make_member("m1")])
        elig_results = [{"team_id": "t1", "status": "INELIGIBLE", "summary": "Team size violation"}]

        run = evaluate_scoring(
            teams=[team],
            signals=None,
            config=cfg,
            eligibility_results=elig_results,
        )
        assert run.teams[0].score_status == ScoreStatus.DISQUALIFIED
        assert run.teams[0].final_score == 0.0

    def test_scoring_works_independently_when_no_eligibility_supplied(self):
        """Scoring operates independently when no eligibility result is provided."""
        cfg = default_scoring_config_store.get("balanced")
        team = make_team("t1", "Gamma", [make_member("m1")])
        run = evaluate_scoring(teams=[team], signals=None, config=cfg)
        assert run.teams[0].eligibility_status is None


# ===========================================================================
# F. Explanations, Reconciliation, and Determinism Tests
# ===========================================================================


class TestExplanationsAndDeterminism:
    def test_weighted_contributions_reconcile_with_final_score(self):
        """The sum of reported criteria contributions exactly equals the reported final score."""
        cfg = default_scoring_config_store.get("balanced")
        team = make_team("t1", "Delta", [make_member("m1")])
        sigs = [
            {
                "member_id": "m1",
                "signals": [
                    {"signal_key": "github_public_repo_count", "category": "technical", "status": "extracted", "value": 7},
                    {"signal_key": "academic_cgpa", "category": "academic", "status": "extracted", "value": 8.5},
                    {"signal_key": "resume_experience_years", "category": "experience", "status": "extracted", "value": 2.5},
                    {"signal_key": "github_profile_verified", "category": "technical", "status": "extracted", "value": True},
                ],
            }
        ]
        run = evaluate_scoring(teams=[team], signals=sigs, config=cfg)
        res = run.teams[0]

        contributions_sum = sum(b.weighted_contribution for b in res.criteria_breakdowns)
        assert res.final_score == pytest.approx(contributions_sum, 0.01)

    def test_deterministic_scoring_and_stable_sorting(self):
        """Identical inputs produce identical output and results are sorted by team_id."""
        cfg = default_scoring_config_store.get("balanced")
        t_b = make_team("team_b", "Bravo", [make_member("m2")])
        t_a = make_team("team_a", "Alpha", [make_member("m1")])

        run1 = evaluate_scoring(teams=[t_b, t_a], signals=None, config=cfg, run_id="r1", evaluated_at="2026-01-01T00:00:00Z")
        run2 = evaluate_scoring(teams=[t_a, t_b], signals=None, config=cfg, run_id="r1", evaluated_at="2026-01-01T00:00:00Z")

        # Sorted by team_id
        assert [t.team_id for t in run1.teams] == ["team_a", "team_b"]
        assert [t.team_id for t in run2.teams] == ["team_a", "team_b"]
        assert run1.model_dump() == run2.model_dump()

    def test_malformed_team_records_error_and_run_continues(self):
        """A malformed team dict records an error while other teams evaluate cleanly."""
        cfg = default_scoring_config_store.get("balanced")
        t_bad = {"invalid": "payload"}
        t_good = make_team("t_good", "Good Team", [make_member("m1")])

        run = evaluate_scoring(teams=[t_bad, t_good], signals=None, config=cfg)
        assert len(run.teams) == 2
        assert run.teams[0].score_status == ScoreStatus.NO_SCORE
        assert run.teams[1].team_id == "t_good"


# ===========================================================================
# G. Configuration Versioning & API Endpoints Tests
# ===========================================================================


class TestConfigurationVersioningAndApi:
    def test_catalog_endpoint_lists_all_options(self):
        resp = client.get("/api/scoring/catalog")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["criterion_types"]) >= 3
        assert len(data["aggregation_methods"]) >= 6
        assert len(data["missing_data_policies"]) >= 2

    def test_configuration_creation_and_version_immutability(self):
        """Updating a configuration creates an immutable v2 while preserving v1."""
        payload = {
            "config_id": "test_cfg",
            "name": "Initial Config",
            "criteria": [
                {
                    "criterion_id": "c1",
                    "name": "Repos",
                    "target_signal_key": "github_public_repo_count",
                    "criterion_type": "numeric_range",
                    "weight": 10.0,
                    "normalization": {"linear_range": {"min_value": 0.0, "max_value": 10.0}},
                }
            ],
        }
        res_create = client.post("/api/scoring/configs", json=payload)
        assert res_create.status_code == 201
        assert res_create.json()["version"] == 1

        # Update to v2
        update_payload = {"name": "Updated Config v2"}
        res_update = client.put("/api/scoring/configs/test_cfg", json=update_payload)
        assert res_update.status_code == 200
        assert res_update.json()["version"] == 2

        # Fetch v1
        v1_resp = client.get("/api/scoring/configs/test_cfg?version=1")
        assert v1_resp.status_code == 200
        assert v1_resp.json()["name"] == "Initial Config"

        # List versions
        ver_resp = client.get("/api/scoring/configs/test_cfg/versions")
        assert ver_resp.json() == [1, 2]

    def test_api_validation_rejects_invalid_configuration_422(self):
        """Invalid configurations return HTTP 422 with structured error details."""
        # Unknown signal key
        bad_payload = {
            "config_id": "bad_cfg",
            "name": "Bad",
            "criteria": [
                {
                    "criterion_id": "c1",
                    "name": "Unknown",
                    "target_signal_key": "completely_fictional_signal",
                    "criterion_type": "numeric_range",
                    "weight": 10.0,
                    "normalization": {"linear_range": {"min_value": 0.0, "max_value": 10.0}},
                }
            ],
        }
        resp = client.post("/api/scoring/configs", json=bad_payload)
        assert resp.status_code == 422
        assert "completely_fictional_signal" in str(resp.json())

    def test_evaluate_endpoint_and_run_persistence(self):
        """POST /api/scoring/evaluate executes scoring and stores run audit."""
        team = {"team_id": "t1", "team_name": "Test", "members": [{"member_id": "m1", "name": "Alice"}]}
        eval_payload = {
            "teams": [team],
            "config_id": "balanced",
        }
        resp = client.post("/api/scoring/evaluate", json=eval_payload)
        assert resp.status_code == 200
        data = resp.json()
        run_id = data["run_id"]
        assert len(data["teams"]) == 1

        # Retrieve run from store
        get_run = client.get(f"/api/scoring/runs/{run_id}")
        assert get_run.status_code == 200
        assert get_run.json()["run_id"] == run_id
        assert get_run.json()["config_id"] == "balanced"

    def test_top_k_when_team_has_fewer_members_than_k(self):
        """When team has fewer members than K, top_k averages all available members."""
        m1 = make_member("m1")
        m2 = make_member("m2")
        team = make_team("t1", "T1", [m1, m2])  # 2 members, K=5

        sigs = {
            "m1": {"github_public_repo_count": make_signal("github_public_repo_count", 4)},  # 0.4
            "m2": {"github_public_repo_count": make_signal("github_public_repo_count", 8)},  # 0.8
        }
        crit = EvaluationCriterion(
            criterion_id="c_topk",
            name="Top K",
            target_signal_key="github_public_repo_count",
            criterion_type=CriterionType.NUMERIC_RANGE,
            weight=1.0,
            aggregation=AggregationMethod.TOP_K,
            top_k_value=5,
            normalization=NormalizationConfig(linear_range=LinearRangeConfig(min_value=0.0, max_value=10.0)),
        )
        cfg = ScoringConfiguration(config_id="topk_cfg", name="TopK Cfg", criteria=[crit])
        res = calculate_team_score(team, cfg, sigs)
        # Average of 2 available: (0.4 + 0.8) / 2 = 0.6 -> * 100 = 60.0
        assert res.final_score == 60.0

    def test_confidence_adjustment_multiplier_and_cutoff(self):
        """Confidence adjustment scales score or drops it if below min_confidence."""
        crit = EvaluationCriterion(
            criterion_id="c_conf",
            name="Conf",
            target_signal_key="resume_experience_years",
            criterion_type=CriterionType.NUMERIC_RANGE,
            weight=1.0,
            confidence_adjustment={"enabled": True, "min_confidence": 0.5},
            normalization=NormalizationConfig(linear_range=LinearRangeConfig(min_value=0.0, max_value=4.0)),
        )
        cfg = ScoringConfiguration(config_id="conf_cfg", name="Conf Cfg", criteria=[crit])

        # 1. High confidence (0.8): raw 4.0 -> norm 1.0 -> scaled by 0.8 -> 0.8 -> * 100 = 80.0
        m1 = make_member("m1")
        sigs_high = {"m1": {"resume_experience_years": make_signal("resume_experience_years", 4.0, confidence=0.8)}}
        res_high = calculate_team_score(make_team("t1", "T1", [m1]), cfg, sigs_high)
        assert res_high.final_score == 80.0

        # 2. Low confidence (0.3 < 0.5 cutoff): treated as unextracted -> missing policy applies
        sigs_low = {"m1": {"resume_experience_years": make_signal("resume_experience_years", 4.0, confidence=0.3)}}
        res_low = calculate_team_score(make_team("t1", "T1", [m1]), cfg, sigs_low)
        # EXCLUDE_AND_RENORMALIZE drops the only criterion -> NO_SCORE
        assert res_low.score_status == ScoreStatus.NO_SCORE
        assert res_low.final_score is None

    def test_get_nonexistent_config_and_run_returns_404(self):
        """Unknown config ID or run ID returns HTTP 404."""
        assert client.get("/api/scoring/configs/nonexistent_cfg_12345").status_code == 404
        assert client.get("/api/scoring/runs/nonexistent_run_12345").status_code == 404
        assert client.get("/api/scoring/configs/nonexistent_cfg_12345/versions").status_code == 404

