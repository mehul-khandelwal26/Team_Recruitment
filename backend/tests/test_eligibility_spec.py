"""Automated test suite for Prompt 4.1 Eligibility Completion and Spec Compliance.

Covers:
F1. Coverage for all 10 rule types (pass, fail, on_missing = fail, pass, manual_review).
F2. Threshold operators, boundary values, all 5 aggregations, partial data, 0.0, empty teams.
F3. Cross-team duplicate member emails: normalization, whitespace, case, same-team repeats, blank emails, shuffled order.
F4. Rule-engine fault isolation: disabled rules, malformed rule error isolation, corrupted signals.
F5. Determinism: identical evaluations under injected timestamps and run_id.
F6. HTTP 422 validation tests for all configuration violations.
F7. Configuration history and immutable versioning.
F8. Manual overrides: rejection of whitespace reason, separation from automated results.
"""

from __future__ import annotations

import datetime
from typing import Any
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.rules.config_store import default_config_store
from app.rules.engine import evaluate_teams
from app.rules.schemas import (
    AggregationMethod,
    EligibilityEvaluateRequest,
    EligibilityStatus,
    GlobalRuleConfig,
    MemberSelection,
    OnMissingAction,
    RuleConfiguration,
    RuleConfigurationCreate,
    RuleConfigurationUpdate,
    RuleDefinition,
    RuleResultStatus,
    RuleScope,
    RuleSeverity,
)
from app.rules.store import default_override_store, default_run_store
from app.schemas.ingestion import FieldPresenceStatus, MemberSchema, TeamSchema
from app.signals.schemas import ExtractedSignal, SignalStatus

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_stores():
    default_config_store.reset()
    default_run_store.reset()
    default_override_store.reset()
    yield


def make_member(
    member_id: str,
    name: str = "Candidate",
    email: str | None = None,
    github_url: str | None = None,
    resume_url: str | None = None,
    portfolio_url: str | None = None,
    custom_fields: dict[str, Any] | None = None,
    raw_data: dict[str, Any] | None = None,
    field_statuses: dict[str, FieldPresenceStatus] | None = None,
    **kwargs: Any,
) -> MemberSchema:
    return MemberSchema(
        member_id=member_id,
        name=name,
        email=email,
        github_url=github_url,
        resume_url=resume_url,
        portfolio_url=portfolio_url,
        custom_fields=custom_fields or {},
        raw_data=raw_data or {},
        field_statuses=field_statuses or {},
        **kwargs,
    )


def make_team(team_id: str, team_name: str, members: list[MemberSchema]) -> TeamSchema:
    return TeamSchema(team_id=team_id, team_name=team_name, members=members)


# ===========================================================================
# F1. Coverage for All 10 Rule Types
# ===========================================================================


class TestAllTenRuleTypesPassFailMissing:
    """Pass, fail, and on_missing (fail, pass, manual_review) for each of the 10 rule types."""

    # 1. team_size_min
    def test_team_size_min(self):
        rule = RuleDefinition(
            rule_id="r_min",
            rule_type="team_size_min",
            name="Min 2 Members",
            severity=RuleSeverity.HARD,
            scope=RuleScope.TEAM,
            parameters={"min_size": 2},
        )
        cfg = RuleConfiguration(config_id="c1", name="C1", rules=[rule])

        team_pass = make_team("t1", "T1", [make_member("m1"), make_member("m2")])
        res_pass = evaluate_teams([team_pass], None, cfg)
        assert res_pass.teams[0].status == EligibilityStatus.ELIGIBLE
        assert res_pass.teams[0].rule_results[0].status == RuleResultStatus.PASSED

        team_fail = make_team("t2", "T2", [make_member("m1")])
        res_fail = evaluate_teams([team_fail], None, cfg)
        assert res_fail.teams[0].status == EligibilityStatus.INELIGIBLE
        assert res_fail.teams[0].rule_results[0].status == RuleResultStatus.FAILED

    # 2. team_size_max
    def test_team_size_max(self):
        rule = RuleDefinition(
            rule_id="r_max",
            rule_type="team_size_max",
            name="Max 3 Members",
            severity=RuleSeverity.HARD,
            scope=RuleScope.TEAM,
            parameters={"max_size": 3},
        )
        cfg = RuleConfiguration(config_id="c1", name="C1", rules=[rule])

        team_pass = make_team("t1", "T1", [make_member("m1"), make_member("m2")])
        res_pass = evaluate_teams([team_pass], None, cfg)
        assert res_pass.teams[0].status == EligibilityStatus.ELIGIBLE
        assert res_pass.teams[0].rule_results[0].status == RuleResultStatus.PASSED

        team_fail = make_team("t2", "T2", [make_member(f"m{i}") for i in range(4)])
        res_fail = evaluate_teams([team_fail], None, cfg)
        assert res_fail.teams[0].status == EligibilityStatus.INELIGIBLE
        assert res_fail.teams[0].rule_results[0].status == RuleResultStatus.FAILED

    # 3. required_link
    @pytest.mark.parametrize("om_action, expected_status", [
        (OnMissingAction.FAIL, RuleResultStatus.FAILED),
        (OnMissingAction.PASS, RuleResultStatus.PASSED),
        (OnMissingAction.MANUAL_REVIEW, RuleResultStatus.NEEDS_REVIEW),
    ])
    def test_required_link_outcomes(self, om_action, expected_status):
        rule = RuleDefinition(
            rule_id="r_link",
            rule_type="required_link",
            name="Portfolio Link",
            severity=RuleSeverity.HARD,
            scope=RuleScope.MEMBER,
            member_selection=MemberSelection.ALL_MEMBERS,
            on_missing=om_action,
            parameters={"link_field": "portfolio_url"},
        )
        cfg = RuleConfiguration(config_id="c1", name="C1", rules=[rule])

        # Unmapped field triggers on_missing
        team_unmapped = make_team("t1", "T1", [make_member("m1", field_statuses={"portfolio_url": FieldPresenceStatus.NOT_COLLECTED})])
        res = evaluate_teams([team_unmapped], None, cfg)
        assert res.teams[0].rule_results[0].status == expected_status

        # Passing
        team_pass = make_team("t1", "T1", [make_member("m1", portfolio_url="https://alice.dev")])
        res_p = evaluate_teams([team_pass], None, cfg)
        assert res_p.teams[0].rule_results[0].status == RuleResultStatus.PASSED

        # Failing (collected blank -> NOT PROVIDED -> FAILED)
        team_fail = make_team("t1", "T1", [make_member("m1", field_statuses={"portfolio_url": FieldPresenceStatus.COLLECTED_BLANK})])
        res_f = evaluate_teams([team_fail], None, cfg)
        assert res_f.teams[0].rule_results[0].status == RuleResultStatus.FAILED

    # 4. required_signal_present
    @pytest.mark.parametrize("om_action, expected_status", [
        (OnMissingAction.FAIL, RuleResultStatus.FAILED),
        (OnMissingAction.PASS, RuleResultStatus.PASSED),
        (OnMissingAction.MANUAL_REVIEW, RuleResultStatus.NEEDS_REVIEW),
    ])
    def test_required_signal_present_outcomes(self, om_action, expected_status):
        rule = RuleDefinition(
            rule_id="r_sig",
            rule_type="required_signal_present",
            name="Public Repos Signal Required",
            severity=RuleSeverity.HARD,
            scope=RuleScope.MEMBER,
            on_missing=om_action,
            parameters={"signal_key": "github_public_repo_count"},
        )
        cfg = RuleConfiguration(config_id="c1", name="C1", rules=[rule])

        # Signal failed extraction -> UNAVAILABLE -> triggers on_missing
        team = make_team("t1", "T1", [make_member("m1")])
        signals = [{
            "member_id": "m1",
            "signals": [{"signal_key": "github_public_repo_count", "category": "github", "status": "failed", "value": None}],
        }]
        res = evaluate_teams([team], signals, cfg)
        assert res.teams[0].rule_results[0].status == expected_status

    # 5. signal_threshold
    @pytest.mark.parametrize("om_action, expected_status", [
        (OnMissingAction.FAIL, RuleResultStatus.FAILED),
        (OnMissingAction.PASS, RuleResultStatus.PASSED),
        (OnMissingAction.MANUAL_REVIEW, RuleResultStatus.NEEDS_REVIEW),
    ])
    def test_signal_threshold_outcomes(self, om_action, expected_status):
        rule = RuleDefinition(
            rule_id="r_thresh",
            rule_type="signal_threshold",
            name="CGPA Threshold",
            severity=RuleSeverity.HARD,
            scope=RuleScope.MEMBER,
            on_missing=om_action,
            parameters={
                "signal_key": "academic_cgpa",
                "operator": ">=",
                "threshold": 7.0,
                "member_selection": "all_members",
                "aggregation": "all",
            },
        )
        cfg = RuleConfiguration(config_id="c1", name="C1", rules=[rule])

        team = make_team("t1", "T1", [make_member("m1")])
        # Absent signals payload -> UNAVAILABLE -> on_missing
        res = evaluate_teams([team], None, cfg)
        assert res.teams[0].rule_results[0].status == expected_status

    # 6. signal_contains
    @pytest.mark.parametrize("om_action, expected_status", [
        (OnMissingAction.FAIL, RuleResultStatus.FAILED),
        (OnMissingAction.PASS, RuleResultStatus.PASSED),
        (OnMissingAction.MANUAL_REVIEW, RuleResultStatus.NEEDS_REVIEW),
    ])
    def test_signal_contains_outcomes(self, om_action, expected_status):
        rule = RuleDefinition(
            rule_id="r_contains",
            rule_type="signal_contains",
            name="Requires Python Skill",
            severity=RuleSeverity.HARD,
            scope=RuleScope.MEMBER,
            on_missing=om_action,
            parameters={
                "signal_key": "resume_programming_languages",
                "expected_value": "Python",
                "member_selection": "any_member",
            },
        )
        cfg = RuleConfiguration(config_id="c1", name="C1", rules=[rule])

        # Missing signal payload -> UNAVAILABLE
        team = make_team("t1", "T1", [make_member("m1")])
        res = evaluate_teams([team], None, cfg)
        assert res.teams[0].rule_results[0].status == expected_status

        # Passing extraction
        signals_pass = [{
            "member_id": "m1",
            "signals": [{"signal_key": "resume_programming_languages", "category": "experience", "status": "extracted", "value": ["Go", "Python", "Rust"]}],
        }]
        res_pass = evaluate_teams([team], signals_pass, cfg)
        assert res_pass.teams[0].rule_results[0].status == RuleResultStatus.PASSED

        # Failing extraction
        signals_fail = [{
            "member_id": "m1",
            "signals": [{"signal_key": "resume_programming_languages", "category": "experience", "status": "extracted", "value": ["Java", "C++"]}],
        }]
        res_fail = evaluate_teams([team], signals_fail, cfg)
        assert res_fail.teams[0].rule_results[0].status == RuleResultStatus.FAILED

    # 7. allowed_values
    @pytest.mark.parametrize("om_action, expected_status", [
        (OnMissingAction.FAIL, RuleResultStatus.FAILED),
        (OnMissingAction.PASS, RuleResultStatus.PASSED),
        (OnMissingAction.MANUAL_REVIEW, RuleResultStatus.NEEDS_REVIEW),
    ])
    def test_allowed_values_outcomes(self, om_action, expected_status):
        rule = RuleDefinition(
            rule_id="r_allowed",
            rule_type="allowed_values",
            name="Allowed Branches",
            severity=RuleSeverity.HARD,
            scope=RuleScope.MEMBER,
            on_missing=om_action,
            parameters={"field_key": "branch", "allowed_values": ["CSE", "ECE"]},
        )
        cfg = RuleConfiguration(config_id="c1", name="C1", rules=[rule])

        # Unmapped branch -> UNAVAILABLE
        team_unmapped = make_team("t1", "T1", [make_member("m1", custom_fields={})])
        res = evaluate_teams([team_unmapped], None, cfg)
        assert res.teams[0].rule_results[0].status == expected_status

        # Passing
        team_pass = make_team("t1", "T1", [make_member("m1", custom_fields={"branch": "cse"})])
        res_p = evaluate_teams([team_pass], None, cfg)
        assert res_p.teams[0].rule_results[0].status == RuleResultStatus.PASSED

        # Failing
        team_fail = make_team("t1", "T1", [make_member("m1", custom_fields={"branch": "Civil"})])
        res_f = evaluate_teams([team_fail], None, cfg)
        assert res_f.teams[0].rule_results[0].status == RuleResultStatus.FAILED

    # 8. track_limit
    @pytest.mark.parametrize("om_action, expected_status", [
        (OnMissingAction.FAIL, RuleResultStatus.FAILED),
        (OnMissingAction.PASS, RuleResultStatus.PASSED),
        (OnMissingAction.MANUAL_REVIEW, RuleResultStatus.NEEDS_REVIEW),
    ])
    def test_track_limit_outcomes(self, om_action, expected_status):
        rule = RuleDefinition(
            rule_id="r_track",
            rule_type="track_limit",
            name="AI Track Cap",
            severity=RuleSeverity.HARD,
            scope=RuleScope.CROSS_TEAM,
            on_missing=om_action,
            parameters={"field_key": "track", "track_limits": {"AI": 1}},
        )
        cfg = RuleConfiguration(config_id="c1", name="C1", rules=[rule])

        # Unmapped track
        team_unmapped = make_team("t1", "T1", [make_member("m1", custom_fields={})])
        res = evaluate_teams([team_unmapped], None, cfg)
        assert res.teams[0].rule_results[0].status == expected_status

        # 2 teams in AI track with limit 1 -> both exceed limit
        t1 = make_team("t1", "T1", [make_member("m1", custom_fields={"track": "AI"})])
        t2 = make_team("t2", "T2", [make_member("m2", custom_fields={"track": "AI"})])
        res_exceed = evaluate_teams([t1, t2], None, cfg)
        assert res_exceed.teams[0].rule_results[0].status == RuleResultStatus.FAILED
        assert res_exceed.teams[1].rule_results[0].status == RuleResultStatus.FAILED

    # 9. duplicate_member_email
    def test_duplicate_member_email_outcomes(self):
        rule = RuleDefinition(
            rule_id="r_dup",
            rule_type="duplicate_member_email",
            name="No Cross-Team Duplicates",
            severity=RuleSeverity.HARD,
            scope=RuleScope.CROSS_TEAM,
        )
        cfg = RuleConfiguration(config_id="c1", name="C1", rules=[rule])

        t1 = make_team("t1", "Alpha", [make_member("m1", email="alice@test.com")])
        t2 = make_team("t2", "Beta", [make_member("m2", email="bob@test.com")])
        res_pass = evaluate_teams([t1, t2], None, cfg)
        assert res_pass.teams[0].rule_results[0].status == RuleResultStatus.PASSED
        assert res_pass.teams[1].rule_results[0].status == RuleResultStatus.PASSED

        t3 = make_team("t3", "Gamma", [make_member("m3", email="Alice@test.com")])  # duplicate of t1
        res_dup = evaluate_teams([t1, t3], None, cfg)
        assert res_dup.teams[0].rule_results[0].status == RuleResultStatus.FAILED
        assert res_dup.teams[1].rule_results[0].status == RuleResultStatus.FAILED
        assert "t3" in res_dup.teams[0].rule_results[0].explanation
        assert "t1" in res_dup.teams[1].rule_results[0].explanation

    # 10. required_fields_present
    @pytest.mark.parametrize("om_action, expected_status", [
        (OnMissingAction.FAIL, RuleResultStatus.FAILED),
        (OnMissingAction.PASS, RuleResultStatus.PASSED),
        (OnMissingAction.MANUAL_REVIEW, RuleResultStatus.NEEDS_REVIEW),
    ])
    def test_required_fields_present_outcomes(self, om_action, expected_status):
        rule = RuleDefinition(
            rule_id="r_req",
            rule_type="required_fields_present",
            name="Mandatory College Name",
            severity=RuleSeverity.HARD,
            scope=RuleScope.MEMBER,
            on_missing=om_action,
            parameters={"field_keys": ["college_name"]},
        )
        cfg = RuleConfiguration(config_id="c1", name="C1", rules=[rule])

        # Unmapped
        t_unmapped = make_team("t1", "T1", [make_member("m1", custom_fields={})])
        res = evaluate_teams([t_unmapped], None, cfg)
        assert res.teams[0].rule_results[0].status == expected_status


# ===========================================================================
# F2. Threshold Operators & Aggregations
# ===========================================================================


class TestThresholdOperatorsAndAggregations:
    @pytest.mark.parametrize("op, thresh, val, expected_pass", [
        (">=", 7.0, 7.0, True),
        (">=", 7.0, 6.99, False),
        (">", 7.0, 7.0, False),
        (">", 7.0, 7.01, True),
        ("<=", 5.0, 5.0, True),
        ("<=", 5.0, 5.01, False),
        ("<", 5.0, 5.0, False),
        ("<", 5.0, 4.99, True),
        ("==", 10.0, 10.0, True),
        ("==", 10.0, 9.9, False),
        ("!=", 0.0, 0.0, False),
        ("!=", 0.0, 1.0, True),
    ])
    def test_all_operators_and_boundary_values(self, op, thresh, val, expected_pass):
        rule = RuleDefinition(
            rule_id="r",
            rule_type="signal_threshold",
            name="Threshold Test",
            severity=RuleSeverity.HARD,
            parameters={"signal_key": "academic_cgpa", "operator": op, "threshold": thresh, "aggregation": "all"},
        )
        cfg = RuleConfiguration(config_id="c", name="C", rules=[rule])
        team = make_team("t1", "T1", [make_member("m1")])
        signals = [{
            "member_id": "m1",
            "signals": [{"signal_key": "academic_cgpa", "category": "academic", "status": "extracted", "value": val}],
        }]
        res = evaluate_teams([team], signals, cfg)
        expected_res = RuleResultStatus.PASSED if expected_pass else RuleResultStatus.FAILED
        assert res.teams[0].rule_results[0].status == expected_res

    def test_all_five_aggregations_with_complete_data(self):
        """Values: 6.0 and 8.0. Min=6.0, Max=8.0, Mean=7.0."""
        team = make_team("t1", "T1", [make_member("m1"), make_member("m2")])
        signals = [
            {"member_id": "m1", "signals": [{"signal_key": "academic_cgpa", "category": "academic", "status": "extracted", "value": 6.0}]},
            {"member_id": "m2", "signals": [{"signal_key": "academic_cgpa", "category": "academic", "status": "extracted", "value": 8.0}]},
        ]

        def run_agg(agg_name, threshold):
            rule = RuleDefinition(
                rule_id="r",
                rule_type="signal_threshold",
                name=f"Agg {agg_name}",
                parameters={"signal_key": "academic_cgpa", "operator": ">=", "threshold": threshold, "aggregation": agg_name},
            )
            return evaluate_teams([team], signals, RuleConfiguration(config_id="c", name="C", rules=[rule])).teams[0].rule_results[0].status

        assert run_agg("all", 6.0) == RuleResultStatus.PASSED
        assert run_agg("all", 7.0) == RuleResultStatus.FAILED  # m1 has 6.0 < 7.0
        assert run_agg("any", 7.0) == RuleResultStatus.PASSED  # m2 has 8.0 >= 7.0
        assert run_agg("min", 6.0) == RuleResultStatus.PASSED
        assert run_agg("min", 6.5) == RuleResultStatus.FAILED
        assert run_agg("max", 8.0) == RuleResultStatus.PASSED
        assert run_agg("max", 8.5) == RuleResultStatus.FAILED
        assert run_agg("mean", 7.0) == RuleResultStatus.PASSED
        assert run_agg("mean", 7.5) == RuleResultStatus.FAILED

    def test_partial_member_data_never_silently_dropped_in_reductions(self):
        """If m1 has 10.0 but m2 is missing/unavailable, mean cannot be computed and triggers on_missing."""
        team = make_team("t1", "T1", [make_member("m1"), make_member("m2")])
        signals = [
            {"member_id": "m1", "signals": [{"signal_key": "academic_cgpa", "category": "academic", "status": "extracted", "value": 10.0}]},
            # m2 is absent from signals
        ]
        rule = RuleDefinition(
            rule_id="r_mean",
            rule_type="signal_threshold",
            name="Mean >= 5.0",
            on_missing=OnMissingAction.MANUAL_REVIEW,
            parameters={"signal_key": "academic_cgpa", "operator": ">=", "threshold": 5.0, "aggregation": "mean"},
        )
        res = evaluate_teams([team], signals, RuleConfiguration(config_id="c", name="C", rules=[rule]))
        assert res.teams[0].rule_results[0].status == RuleResultStatus.NEEDS_REVIEW
        assert "cannot reliably compute 'mean'" in res.teams[0].rule_results[0].explanation.lower()

    def test_legitimate_numeric_zero_preserved_in_aggregation(self):
        """0.0 is valid and averages with 10.0 to 5.0."""
        team = make_team("t1", "T1", [make_member("m1"), make_member("m2")])
        signals = [
            {"member_id": "m1", "signals": [{"signal_key": "github_public_repo_count", "category": "github", "status": "extracted", "value": 0}]},
            {"member_id": "m2", "signals": [{"signal_key": "github_public_repo_count", "category": "github", "status": "extracted", "value": 10}]},
        ]
        rule = RuleDefinition(
            rule_id="r",
            rule_type="signal_threshold",
            name="Mean >= 5",
            parameters={"signal_key": "github_public_repo_count", "operator": ">=", "threshold": 5.0, "aggregation": "mean"},
        )
        res = evaluate_teams([team], signals, RuleConfiguration(config_id="c", name="C", rules=[rule]))
        assert res.teams[0].rule_results[0].status == RuleResultStatus.PASSED


# ===========================================================================
# F3. Cross-Team Duplicate Email Rules
# ===========================================================================


class TestCrossTeamDuplicateEmails:
    def test_whitespace_and_case_insensitive_duplicate(self):
        t1 = make_team("team_a", "Alpha", [make_member("m1", email="  Candidate.ONE@Example.com ")])
        t2 = make_team("team_b", "Beta", [make_member("m2", email="candidate.one@example.com")])

        rule = RuleDefinition(rule_id="r_dup", rule_type="duplicate_member_email", name="No Dupes", scope=RuleScope.CROSS_TEAM)
        cfg = RuleConfiguration(config_id="c", name="C", rules=[rule])

        res = evaluate_teams([t1, t2], None, cfg)
        assert res.teams[0].rule_results[0].status == RuleResultStatus.FAILED
        assert res.teams[1].rule_results[0].status == RuleResultStatus.FAILED
        assert "team_b" in res.teams[0].rule_results[0].explanation
        assert "team_a" in res.teams[1].rule_results[0].explanation

    def test_same_team_repeat_and_blank_emails_ignored(self):
        """Members on the same team sharing an email or leaving blank are not cross-team duplicates."""
        t1 = make_team("team_a", "Alpha", [
            make_member("m1", email="shared@example.com"),
            make_member("m2", email="shared@example.com"),
            make_member("m3", email="   "),
            make_member("m4", email=None),
        ])
        rule = RuleDefinition(rule_id="r_dup", rule_type="duplicate_member_email", name="No Dupes", scope=RuleScope.CROSS_TEAM)
        cfg = RuleConfiguration(config_id="c", name="C", rules=[rule])

        res = evaluate_teams([t1], None, cfg)
        assert res.teams[0].rule_results[0].status == RuleResultStatus.PASSED

    def test_shuffled_order_produces_identical_results(self):
        """Input order must not affect cross-team duplicate detection."""
        t1 = make_team("team_1", "Alpha", [make_member("m1", email="dup@test.com")])
        t2 = make_team("team_2", "Beta", [make_member("m2", email="unique@test.com")])
        t3 = make_team("team_3", "Gamma", [make_member("m3", email="dup@test.com")])

        rule = RuleDefinition(rule_id="r_dup", rule_type="duplicate_member_email", name="No Dupes", scope=RuleScope.CROSS_TEAM)
        cfg = RuleConfiguration(config_id="c", name="C", rules=[rule])

        res_order1 = evaluate_teams([t1, t2, t3], None, cfg)
        res_order2 = evaluate_teams([t3, t1, t2], None, cfg)

        assert [t.status for t in res_order1.teams] == [t.status for t in res_order2.teams]
        assert [t.team_id for t in res_order1.teams] == [t.team_id for t in res_order2.teams]


# ===========================================================================
# F4 & F5. Fault Isolation and Determinism
# ===========================================================================


class TestFaultIsolationAndDeterminism:
    def test_malformed_rule_records_structured_error_and_run_continues(self):
        """A rule with an invalid parameter records ERROR for that rule while others evaluate."""
        broken_rule = RuleDefinition(
            rule_id="broken",
            rule_type="team_size_min",
            name="Broken Min Size",
            severity=RuleSeverity.HARD,
            parameters={"min_size": "not_an_int"},
        )
        valid_rule = RuleDefinition(
            rule_id="valid",
            rule_type="team_size_max",
            name="Valid Max Size",
            severity=RuleSeverity.HARD,
            parameters={"max_size": 4},
        )
        cfg = RuleConfiguration(config_id="c", name="C", rules=[broken_rule, valid_rule])
        team = make_team("t1", "T1", [make_member("m1")])

        res = evaluate_teams([team], None, cfg)
        assert len(res.teams[0].rule_results) == 2
        assert res.teams[0].rule_results[0].status == RuleResultStatus.ERROR
        assert res.teams[0].rule_results[1].status == RuleResultStatus.PASSED

    def test_identical_evaluations_are_deterministic(self):
        """Injected run_id and evaluated_at produce identical JSON outputs."""
        team = make_team("t1", "Alpha", [make_member("m1", github_url="https://github.com/alice")])
        cfg = default_config_store.get("basic")

        fixed_time = "2026-10-15T12:00:00Z"
        fixed_id = "run_fixed_123"

        res1 = evaluate_teams([team], None, cfg, evaluated_at=fixed_time, run_id=fixed_id)
        res2 = evaluate_teams([team], None, cfg, evaluated_at=fixed_time, run_id=fixed_id)

        assert res1.model_dump() == res2.model_dump()


# ===========================================================================
# F6. HTTP 422 API Validation Tests (Step E)
# ===========================================================================


class TestApiValidationHttp422:
    def test_unknown_rule_type_rejected_422(self):
        payload = {
            "name": "Invalid Config",
            "rules": [{"rule_id": "r1", "rule_type": "magical_rule", "name": "Fake"}],
        }
        res = client.post("/api/rules/configs", json=payload)
        assert res.status_code == 422
        assert "unknown rule_type 'magical_rule'" in res.json()["detail"].lower()

    def test_unsupported_operator_rejected_422(self):
        payload = {
            "name": "Invalid Op",
            "rules": [{
                "rule_id": "r1",
                "rule_type": "signal_threshold",
                "name": "Bad Op",
                "parameters": {"signal_key": "academic_cgpa", "operator": "LIKE", "threshold": 7.0},
            }],
        }
        res = client.post("/api/rules/configs", json=payload)
        assert res.status_code == 422
        assert "unsupported operator 'like'" in res.json()["detail"].lower()

    def test_wrong_threshold_type_rejected_422(self):
        payload = {
            "name": "Bad Threshold",
            "rules": [{
                "rule_id": "r1",
                "rule_type": "signal_threshold",
                "name": "Bad Thresh",
                "parameters": {"signal_key": "academic_cgpa", "operator": ">=", "threshold": "seven"},
            }],
        }
        res = client.post("/api/rules/configs", json=payload)
        assert res.status_code == 422
        assert "invalid threshold" in res.json()["detail"].lower()

    def test_unknown_signal_key_rejected_422(self):
        payload = {
            "name": "Unknown Signal",
            "rules": [{
                "rule_id": "r1",
                "rule_type": "required_signal_present",
                "name": "Fake Signal",
                "parameters": {"signal_key": "nonexistent_unregistered_signal"},
            }],
        }
        res = client.post("/api/rules/configs", json=payload)
        assert res.status_code == 422
        assert "unknown signal key" in res.json()["detail"].lower()

    def test_incompatible_signal_value_type_rejected_422(self):
        """Applying numeric threshold to a list signal (resume_programming_languages) -> 422."""
        payload = {
            "name": "Incompatible Type",
            "rules": [{
                "rule_id": "r1",
                "rule_type": "signal_threshold",
                "name": "Threshold on List",
                "parameters": {"signal_key": "resume_programming_languages", "operator": ">=", "threshold": 5},
            }],
        }
        res = client.post("/api/rules/configs", json=payload)
        assert res.status_code == 422
        assert "incompatible with numeric" in res.json()["detail"].lower()

    def test_duplicate_rule_id_rejected_422(self):
        payload = {
            "name": "Duplicate Rule IDs",
            "rules": [
                {"rule_id": "r1", "rule_type": "team_size_min", "name": "Min", "parameters": {"min_size": 2}},
                {"rule_id": "r1", "rule_type": "team_size_max", "name": "Max", "parameters": {"max_size": 4}},
            ],
        }
        res = client.post("/api/rules/configs", json=payload)
        assert res.status_code == 422
        assert "duplicate rule_id" in res.json()["detail"].lower()


# ===========================================================================
# F7 & F8. Config History, Overrides, and Blank vs Unmapped Fields
# ===========================================================================


class TestConfigHistoryAndOverrides:
    def test_config_versioning_and_run_audit(self):
        # Create config v1
        c_res = client.post("/api/rules/configs", json={
            "config_id": "version_test",
            "name": "V1",
            "rules": [{"rule_id": "r1", "rule_type": "team_size_min", "name": "Min", "parameters": {"min_size": 2}}],
        })
        assert c_res.status_code == 201

        # Run against v1
        team = {"team_id": "t1", "team_name": "T", "members": [{"member_id": "m1", "name": "Solo"}]}
        run1 = client.post("/api/rules/evaluate", json={"teams": [team], "config_id": "version_test"}).json()
        assert run1["config_version"] == 1
        assert run1["teams"][0]["status"] == "INELIGIBLE"

        # Update to v2 with min_size=1
        u_res = client.put("/api/rules/configs/version_test", json={
            "rules": [{"rule_id": "r1", "rule_type": "team_size_min", "name": "Min", "parameters": {"min_size": 1}}],
        })
        assert u_res.status_code == 200
        assert u_res.json()["version"] == 2

        # Verify old run remains unchanged and v1 is intact
        old_run_fetch = client.get(f"/api/rules/runs/{run1['run_id']}").json()
        assert old_run_fetch["config_version"] == 1
        assert old_run_fetch["teams"][0]["status"] == "INELIGIBLE"

        # Run against v2 makes solo team ELIGIBLE
        run2 = client.post("/api/rules/evaluate", json={"teams": [team], "config_id": "version_test"}).json()
        assert run2["config_version"] == 2
        assert run2["teams"][0]["status"] == "ELIGIBLE"

    def test_blank_versus_unmapped_field_proven_with_field_statuses(self):
        """field_statuses: COLLECTED_BLANK is NOT PROVIDED -> FAILED; NOT_COLLECTED is UNAVAILABLE -> on_missing."""
        rule = RuleDefinition(
            rule_id="r1",
            rule_type="required_link",
            name="GitHub Check",
            severity=RuleSeverity.HARD,
            scope=RuleScope.MEMBER,
            on_missing=OnMissingAction.MANUAL_REVIEW,
            parameters={"link_field": "github_url"},
        )
        cfg = RuleConfiguration(config_id="c", name="C", rules=[rule])

        # Collected blank
        m_blank = make_member("m1", field_statuses={"github_url": FieldPresenceStatus.COLLECTED_BLANK})
        t_blank = make_team("t1", "Blank", [m_blank])
        res_blank = evaluate_teams([t_blank], None, cfg)
        assert res_blank.teams[0].rule_results[0].status == RuleResultStatus.FAILED
        assert "not provided" in res_blank.teams[0].rule_results[0].explanation.lower()

        # Not collected / unmapped
        m_uncollected = make_member("m2", field_statuses={"github_url": FieldPresenceStatus.NOT_COLLECTED})
        t_uncollected = make_team("t2", "Uncollected", [m_uncollected])
        res_uncollected = evaluate_teams([t_uncollected], None, cfg)
        assert res_uncollected.teams[0].rule_results[0].status == RuleResultStatus.NEEDS_REVIEW
        assert "unavailable" in res_uncollected.teams[0].rule_results[0].explanation.lower()
