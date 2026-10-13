"""Automated test suite for the deterministic eligibility rules engine (Prompt 4).

Covers:
1. Catalog descriptors for all 10 rule types.
2. Default presets (Basic, Strict, Open to Solos) and verification of Condition 3 (no hard resume rules).
3. Configuration versioning and immutability.
4. Missing data contradiction resolution:
   - NOT_APPLICABLE = NOT PROVIDED (rule FAILS)
   - FAILED / PENDING / absent payload = UNAVAILABLE (on_missing applies)
5. Strict numeric safety (reject bool, NaN, infinity; zero is valid).
6. Field lookup order (custom_fields -> raw_data -> canonical).
7. Team lead scope resolution via global_config.lead_field.
8. Team input validation fault isolation & sorting by team_id.
9. Hard vs Soft rule severity semantics and team status determination.
10. Data completeness computation and zero-rule protection.
11. Manual overrides (mandatory reason, original preserved, merged view).
12. End-to-end API evaluation requests producing ELIGIBLE, INELIGIBLE, and NEEDS_REVIEW.
"""

from __future__ import annotations

import math
from typing import Any
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.rules.config_store import default_config_store
from app.rules.engine import evaluate_teams
from app.rules.presets import get_default_presets
from app.rules.schemas import (
    EligibilityEvaluateRequest,
    EligibilityStatus,
    GlobalRuleConfig,
    ManualOverrideCreate,
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
from app.schemas.ingestion import MemberSchema, TeamSchema
from app.signals.schemas import ExtractedSignal, SignalStatus

client = TestClient(app)


# ---------------------------------------------------------------------------
# Test Isolation Fixture
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_in_memory_stores():
    """Reset all module-level in-memory stores before each test."""
    default_config_store.reset()
    default_run_store.reset()
    default_override_store.reset()
    yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_member(
    member_id: str,
    name: str = "Candidate",
    github_url: str | None = None,
    cgpa: str | None = None,
    academic_year: str | None = None,
    custom_fields: dict[str, Any] | None = None,
    raw_data: dict[str, Any] | None = None,
) -> MemberSchema:
    return MemberSchema(
        member_id=member_id,
        name=name,
        github_url=github_url,
        cgpa=cgpa,
        academic_year=academic_year,
        custom_fields=custom_fields or {},
        raw_data=raw_data or {},
    )


def make_team(team_id: str, team_name: str, members: list[MemberSchema]) -> TeamSchema:
    return TeamSchema(team_id=team_id, team_name=team_name, members=members)


# ---------------------------------------------------------------------------
# 1. Catalog & Presets Tests
# ---------------------------------------------------------------------------


class TestCatalogAndPresets:
    def test_catalog_endpoint_lists_all_ten_rule_types(self):
        resp = client.get("/api/rules/catalog")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 10
        rule_types = {item["rule_type"] for item in items}
        expected = {
            "team_size_range",
            "required_link",
            "required_fields_present",
            "required_signal_present",
            "cgpa_minimum",
            "normalized_cgpa_minimum",
            "github_repos_minimum",
            "academic_year_range",
            "allowed_values",
            "custom_signal_threshold",
        }
        assert rule_types == expected

    def test_presets_exist_in_config_store(self):
        configs = default_config_store.list_latest()
        config_ids = {c.config_id for c in configs}
        assert "basic" in config_ids
        assert "strict" in config_ids
        assert "open_solo" in config_ids

    def test_presets_condition_3_no_hard_rules_depend_on_resume_signals(self):
        """Condition 3: No preset may contain a hard rule that depends on resume signals."""
        resume_signal_keys = {
            "resume_extracted_skills",
            "resume_programming_languages",
            "resume_frameworks_libraries",
            "resume_databases",
            "resume_tools_technologies",
            "resume_projects",
            "resume_education",
            "resume_degree_level",
            "resume_experience",
            "resume_experience_years",
            "resume_certifications_achievements",
            "resume_external_links",
        }

        presets = get_default_presets()
        for preset in presets:
            for rule in preset.rules:
                if rule.severity == RuleSeverity.HARD:
                    # Check signal key
                    sig_key = rule.parameters.get("signal_key")
                    assert sig_key not in resume_signal_keys, (
                        f"Preset '{preset.config_id}' has HARD rule '{rule.rule_id}' depending on resume signal '{sig_key}'"
                    )
                    # Check link type
                    link_type = rule.parameters.get("link_type")
                    assert link_type != "resume_url", (
                        f"Preset '{preset.config_id}' has HARD rule '{rule.rule_id}' with link_type='resume_url'"
                    )


# ---------------------------------------------------------------------------
# 2. Configuration Versioning & Immutability Tests
# ---------------------------------------------------------------------------


class TestConfigurationVersioning:
    def test_create_and_version_update(self):
        # 1. Create config version 1
        create_payload = {
            "config_id": "hackathon_v1",
            "name": "Hackathon Config",
            "description": "Initial version",
            "rules": [
                {
                    "rule_id": "r1",
                    "rule_type": "team_size_range",
                    "name": "Team Size",
                    "severity": "hard",
                    "parameters": {"min_size": 2, "max_size": 4},
                }
            ],
        }
        res = client.post("/api/rules/configs", json=create_payload)
        assert res.status_code == 201
        data = res.json()
        assert data["version"] == 1
        assert data["name"] == "Hackathon Config"

        # 2. Update config -> creates version 2
        update_payload = {
            "name": "Hackathon Config Updated",
            "rules": [
                {
                    "rule_id": "r1",
                    "rule_type": "team_size_range",
                    "name": "Team Size",
                    "severity": "hard",
                    "parameters": {"min_size": 3, "max_size": 5},
                }
            ],
        }
        res_update = client.put("/api/rules/configs/hackathon_v1", json=update_payload)
        assert res_update.status_code == 200
        data_v2 = res_update.json()
        assert data_v2["version"] == 2
        assert data_v2["name"] == "Hackathon Config Updated"

        # 3. Verify version 1 is unchanged (immutability)
        res_v1 = client.get("/api/rules/configs/hackathon_v1?version=1")
        assert res_v1.status_code == 200
        assert res_v1.json()["version"] == 1
        assert res_v1.json()["name"] == "Hackathon Config"
        assert res_v1.json()["rules"][0]["parameters"]["min_size"] == 2

        # 4. Listing versions returns [1, 2]
        res_vers = client.get("/api/rules/configs/hackathon_v1/versions")
        assert res_vers.status_code == 200
        assert res_vers.json() == [1, 2]


# ---------------------------------------------------------------------------
# 3. Missing Data Contradiction Resolution Tests
# ---------------------------------------------------------------------------


class TestMissingDataContradictionResolution:
    def test_not_applicable_is_not_provided_and_fails_rule(self):
        """SignalStatus.NOT_APPLICABLE means input missing -> NOT PROVIDED -> rule FAILS."""
        team = make_team("t1", "Alpha", [make_member("m1")])

        # Signal academic_cgpa has status NOT_APPLICABLE
        signals = [
            {
                "member_id": "m1",
                "signals": [
                    {
                        "signal_key": "academic_cgpa",
                        "category": "academic",
                        "status": "not_applicable",
                        "value": None,
                    }
                ],
            }
        ]

        cfg = RuleConfiguration(
            config_id="test_cfg",
            name="Test",
            rules=[
                RuleDefinition(
                    rule_id="cgpa_rule",
                    rule_type="cgpa_minimum",
                    name="CGPA Min",
                    severity=RuleSeverity.HARD,
                    scope=RuleScope.ALL_MEMBERS,
                    on_missing=OnMissingAction.MANUAL_REVIEW,
                    parameters={"min_cgpa": 7.0},
                )
            ],
        )

        res = evaluate_teams([team], signals, cfg)
        assert res.teams[0].status == EligibilityStatus.INELIGIBLE
        assert res.teams[0].rule_results[0].status == RuleResultStatus.FAILED
        assert "not provided" in res.teams[0].rule_results[0].explanation.lower()

    def test_failed_signal_is_unavailable_and_triggers_on_missing(self):
        """SignalStatus.FAILED means extraction broke -> UNAVAILABLE -> triggers on_missing."""
        team = make_team("t1", "Alpha", [make_member("m1")])

        # Signal academic_cgpa has status FAILED (e.g. parser exception)
        signals = [
            {
                "member_id": "m1",
                "signals": [
                    {
                        "signal_key": "academic_cgpa",
                        "category": "academic",
                        "status": "failed",
                        "value": None,
                        "error_message": "Parser timeout",
                    }
                ],
            }
        ]

        # Config with on_missing = manual_review -> NEEDS_REVIEW
        cfg = RuleConfiguration(
            config_id="test_cfg",
            name="Test",
            rules=[
                RuleDefinition(
                    rule_id="cgpa_rule",
                    rule_type="cgpa_minimum",
                    name="CGPA Min",
                    severity=RuleSeverity.HARD,
                    scope=RuleScope.ALL_MEMBERS,
                    on_missing=OnMissingAction.MANUAL_REVIEW,
                    parameters={"min_cgpa": 7.0},
                )
            ],
        )

        res = evaluate_teams([team], signals, cfg)
        assert res.teams[0].status == EligibilityStatus.NEEDS_REVIEW
        assert res.teams[0].rule_results[0].status == RuleResultStatus.NEEDS_REVIEW
        assert res.teams[0].rule_results[0].is_evaluable is False

    def test_absent_signals_payload_is_unavailable_and_triggers_on_missing(self):
        """Absent signals payload is treated as UNAVAILABLE, not failed."""
        team = make_team("t1", "Alpha", [make_member("m1")])

        cfg = RuleConfiguration(
            config_id="test_cfg",
            name="Test",
            rules=[
                RuleDefinition(
                    rule_id="repo_rule",
                    rule_type="github_repos_minimum",
                    name="Repo Check",
                    severity=RuleSeverity.HARD,
                    scope=RuleScope.ANY_MEMBER,
                    on_missing=OnMissingAction.MANUAL_REVIEW,
                    parameters={"min_repos": 1},
                )
            ],
        )

        # No signals passed at all
        res = evaluate_teams([team], signals=None, config=cfg)
        assert res.teams[0].status == EligibilityStatus.NEEDS_REVIEW
        assert res.teams[0].rule_results[0].status == RuleResultStatus.NEEDS_REVIEW
        assert res.teams[0].rule_results[0].is_evaluable is False


# ---------------------------------------------------------------------------
# 4. Strict Numeric Safety Tests
# ---------------------------------------------------------------------------


class TestNumericSafety:
    def test_booleans_nan_and_inf_rejected_as_unavailable(self):
        """Condition 2: booleans, NaN, and infinity must be rejected as UNAVAILABLE."""
        team = make_team("t1", "Alpha", [make_member("m1")])

        cfg = RuleConfiguration(
            config_id="test_cfg",
            name="Test",
            rules=[
                RuleDefinition(
                    rule_id="thresh_rule",
                    rule_type="custom_signal_threshold",
                    name="Score Threshold",
                    severity=RuleSeverity.HARD,
                    scope=RuleScope.ALL_MEMBERS,
                    on_missing=OnMissingAction.MANUAL_REVIEW,
                    parameters={"signal_key": "custom_metric", "threshold": 50, "operator": ">="},
                )
            ],
        )

        # Test boolean True (which Python treats as 1)
        signals_bool = [
            {
                "member_id": "m1",
                "signals": [{"signal_key": "custom_metric", "category": "tech", "status": "extracted", "value": True}],
            }
        ]
        res_bool = evaluate_teams([team], signals_bool, cfg)
        assert res_bool.teams[0].rule_results[0].status == RuleResultStatus.NEEDS_REVIEW
        assert res_bool.teams[0].rule_results[0].is_evaluable is False

        # Test NaN
        signals_nan = [
            {
                "member_id": "m1",
                "signals": [{"signal_key": "custom_metric", "category": "tech", "status": "extracted", "value": float("nan")}],
            }
        ]
        res_nan = evaluate_teams([team], signals_nan, cfg)
        assert res_nan.teams[0].rule_results[0].status == RuleResultStatus.NEEDS_REVIEW

        # Test Infinity
        signals_inf = [
            {
                "member_id": "m1",
                "signals": [{"signal_key": "custom_metric", "category": "tech", "status": "extracted", "value": float("inf")}],
            }
        ]
        res_inf = evaluate_teams([team], signals_inf, cfg)
        assert res_inf.teams[0].rule_results[0].status == RuleResultStatus.NEEDS_REVIEW

    def test_zero_is_valid_numeric_value(self):
        """Zero (0, 0.0) is a valid extracted value and must not be treated as missing."""
        team = make_team("t1", "Alpha", [make_member("m1")])

        cfg = RuleConfiguration(
            config_id="test_cfg",
            name="Test",
            rules=[
                RuleDefinition(
                    rule_id="repos_rule",
                    rule_type="github_repos_minimum",
                    name="Repos >= 0",
                    severity=RuleSeverity.HARD,
                    scope=RuleScope.ALL_MEMBERS,
                    parameters={"min_repos": 0},
                )
            ],
        )

        signals_zero = [
            {
                "member_id": "m1",
                "signals": [{"signal_key": "github_public_repo_count", "category": "technical", "status": "extracted", "value": 0}],
            }
        ]
        res = evaluate_teams([team], signals_zero, cfg)
        assert res.teams[0].status == EligibilityStatus.ELIGIBLE
        assert res.teams[0].rule_results[0].status == RuleResultStatus.PASSED
        assert res.teams[0].rule_results[0].is_evaluable is True


# ---------------------------------------------------------------------------
# 5. Field Lookup Precedence Tests
# ---------------------------------------------------------------------------


class TestFieldLookupPrecedence:
    def test_custom_fields_takes_precedence_over_raw_and_canonical(self):
        """Lookup order: custom_fields -> raw_data -> canonical."""
        # custom_fields says "AI", raw_data says "Web", canonical doesn't have track
        member = make_member(
            "m1",
            custom_fields={"track": "AI"},
            raw_data={"track": "Web"},
        )
        team = make_team("t1", "Alpha", [member])

        cfg = RuleConfiguration(
            config_id="test_cfg",
            name="Test",
            rules=[
                RuleDefinition(
                    rule_id="track_rule",
                    rule_type="allowed_values",
                    name="Allowed Tracks",
                    severity=RuleSeverity.HARD,
                    parameters={"field_key": "track", "allowed_values": ["AI"]},
                )
            ],
        )

        res = evaluate_teams([team], None, cfg)
        assert res.teams[0].status == EligibilityStatus.ELIGIBLE
        assert res.teams[0].rule_results[0].status == RuleResultStatus.PASSED

    def test_raw_data_used_when_custom_fields_lacks_key(self):
        member = make_member(
            "m1",
            custom_fields={},
            raw_data={"stream": "Computer Science"},
        )
        team = make_team("t1", "Alpha", [member])

        cfg = RuleConfiguration(
            config_id="test_cfg",
            name="Test",
            rules=[
                RuleDefinition(
                    rule_id="stream_rule",
                    rule_type="allowed_values",
                    name="Stream Check",
                    severity=RuleSeverity.HARD,
                    parameters={"field_key": "stream", "allowed_values": ["computer science"]},
                )
            ],
        )

        res = evaluate_teams([team], None, cfg)
        assert res.teams[0].status == EligibilityStatus.ELIGIBLE
        assert res.teams[0].rule_results[0].status == RuleResultStatus.PASSED


# ---------------------------------------------------------------------------
# 6. Team Lead Scope Resolution Tests
# ---------------------------------------------------------------------------


class TestTeamLeadScope:
    def test_team_lead_resolved_via_global_config_lead_field(self):
        m1 = make_member("m1", name="Lead Alice", custom_fields={"role": "Team Lead"}, github_url="https://github.com/alice")
        m2 = make_member("m2", name="Dev Bob", custom_fields={"role": "Member"}, github_url=None)
        team = make_team("t1", "Alpha", [m1, m2])

        cfg = RuleConfiguration(
            config_id="lead_cfg",
            name="Lead Must Have GitHub",
            global_config=GlobalRuleConfig(lead_field="role"),
            rules=[
                RuleDefinition(
                    rule_id="lead_github",
                    rule_type="required_link",
                    name="Lead GitHub Link",
                    severity=RuleSeverity.HARD,
                    scope=RuleScope.TEAM_LEAD,
                    parameters={"link_type": "github_url"},
                )
            ],
        )

        res = evaluate_teams([team], None, cfg)
        assert res.teams[0].status == EligibilityStatus.ELIGIBLE
        assert res.teams[0].rule_results[0].status == RuleResultStatus.PASSED
        assert "lead alice" in res.teams[0].rule_results[0].explanation.lower()

    def test_unresolved_team_lead_triggers_on_missing(self):
        """When no member has the lead value, lead is NOT assumed to be member 1 -> UNAVAILABLE."""
        m1 = make_member("m1", name="Dev 1", custom_fields={"role": "Contributor"})
        m2 = make_member("m2", name="Dev 2", custom_fields={"role": "Contributor"})
        team = make_team("t1", "Alpha", [m1, m2])

        cfg = RuleConfiguration(
            config_id="lead_cfg",
            name="Lead Rule",
            global_config=GlobalRuleConfig(lead_field="role"),
            rules=[
                RuleDefinition(
                    rule_id="lead_github",
                    rule_type="required_link",
                    name="Lead GitHub Link",
                    severity=RuleSeverity.HARD,
                    scope=RuleScope.TEAM_LEAD,
                    on_missing=OnMissingAction.MANUAL_REVIEW,
                    parameters={"link_type": "github_url"},
                )
            ],
        )

        res = evaluate_teams([team], None, cfg)
        assert res.teams[0].status == EligibilityStatus.NEEDS_REVIEW
        assert res.teams[0].rule_results[0].status == RuleResultStatus.NEEDS_REVIEW
        assert "could not be determined" in res.teams[0].rule_results[0].explanation.lower()


# ---------------------------------------------------------------------------
# 7. Team Input Fault Isolation & Deterministic Sorting Tests
# ---------------------------------------------------------------------------


class TestTeamInputFaultIsolation:
    def test_invalid_team_dict_records_error_and_run_continues(self):
        """Condition 5: Invalid team dict gets structured error, run continues, sorted by team_id."""
        valid_team = {
            "team_id": "team_2",
            "team_name": "Valid Beta",
            "members": [{"member_id": "m1", "name": "Bob"}],
        }
        invalid_team = {
            "team_id": "team_1",
            "team_name": "Broken Alpha",
            "members": "not_a_list_of_members",  # invalid schema
        }

        cfg = default_config_store.get("basic")

        res = evaluate_teams([valid_team, invalid_team], None, cfg)
        assert len(res.teams) == 2
        # Deterministically sorted: team_1, then team_2
        assert res.teams[0].team_id == "team_1"
        assert res.teams[1].team_id == "team_2"

        # Invalid team receives structured error
        assert res.teams[0].status == EligibilityStatus.INELIGIBLE
        assert len(res.teams[0].errors) > 0
        assert "invalid team structure" in res.teams[0].reasons[0].lower()


# ---------------------------------------------------------------------------
# 8. Hard vs Soft Rule Severity Tests
# ---------------------------------------------------------------------------


class TestHardVsSoftRules:
    def test_soft_rule_failure_does_not_disqualify_team(self):
        """Soft rules do NOT affect ELIGIBLE/INELIGIBLE team status."""
        team = make_team("t1", "Alpha", [make_member("m1", name="Alice", github_url="https://github.com/alice")])

        cfg = RuleConfiguration(
            config_id="mixed_cfg",
            name="Mixed Severity",
            rules=[
                RuleDefinition(
                    rule_id="hard_link",
                    rule_type="required_link",
                    name="GitHub Required",
                    severity=RuleSeverity.HARD,
                    scope=RuleScope.ANY_MEMBER,
                    parameters={"link_type": "github_url"},
                ),
                RuleDefinition(
                    rule_id="soft_cgpa",
                    rule_type="cgpa_minimum",
                    name="CGPA Advisory",
                    severity=RuleSeverity.SOFT,
                    scope=RuleScope.ALL_MEMBERS,
                    parameters={"min_cgpa": 9.5},
                ),
            ],
        )

        signals = [
            {
                "member_id": "m1",
                "signals": [
                    {"signal_key": "academic_cgpa", "category": "academic", "status": "extracted", "value": 7.5}
                ],
            }
        ]

        res = evaluate_teams([team], signals, cfg)
        # Soft rule failed, but hard rule passed -> Team is ELIGIBLE!
        assert res.teams[0].status == EligibilityStatus.ELIGIBLE
        assert res.teams[0].rule_results[1].status == RuleResultStatus.FAILED
        assert res.teams[0].rule_results[1].severity == RuleSeverity.SOFT


# ---------------------------------------------------------------------------
# 9. Data Completeness Tests
# ---------------------------------------------------------------------------


class TestDataCompleteness:
    def test_completeness_ratio_and_zero_rules_handling(self):
        team = make_team(
            "t1",
            "Alpha",
            [
                make_member(
                    "m1",
                    github_url="https://github.com/alice",
                    raw_data={"name": "Alice", "github_url": "https://github.com/alice"},
                )
            ],
        )

        # Config with 2 active rules: 1 evaluable, 1 unavailable (unmapped field)
        cfg = RuleConfiguration(
            config_id="comp_cfg",
            name="Completeness Test",
            rules=[
                RuleDefinition(
                    rule_id="r1",
                    rule_type="required_link",
                    name="GitHub",
                    severity=RuleSeverity.HARD,
                    parameters={"link_type": "github_url"},
                ),
                RuleDefinition(
                    rule_id="r2",
                    rule_type="required_fields_present",
                    name="Custom Track",
                    severity=RuleSeverity.HARD,
                    parameters={"field_keys": ["unmapped_special_track"]},  # unmapped -> UNAVAILABLE
                ),
            ],
        )

        res = evaluate_teams([team], None, cfg)
        # 1 evaluable out of 2 = 0.5
        assert res.teams[0].data_completeness == 0.5

    def test_zero_applicable_rules_returns_none(self):
        team = make_team("t1", "Alpha", [make_member("m1")])
        cfg = RuleConfiguration(config_id="empty_cfg", name="Empty", rules=[])

        res = evaluate_teams([team], None, cfg)
        assert res.teams[0].data_completeness is None


# ---------------------------------------------------------------------------
# 10. Manual Overrides Tests
# ---------------------------------------------------------------------------


class TestManualOverrides:
    def test_apply_and_merge_manual_override(self):
        team = {
            "team_id": "team_ineligible",
            "team_name": "Solo Dev",
            "members": [{"member_id": "m1", "name": "Solo"}],
        }

        # Run with basic preset (requires min 2 members -> INELIGIBLE)
        run_res = client.post("/api/rules/evaluate", json={"teams": [team], "config_id": "basic"})
        assert run_res.status_code == 200
        run_data = run_res.json()
        run_id = run_data["run_id"]
        assert run_data["teams"][0]["status"] == "INELIGIBLE"

        # Apply override to make team ELIGIBLE
        override_payload = {
            "override_status": "ELIGIBLE",
            "reason": "Solo developer granted special exemption by organizer.",
            "overridden_by": "lead_organizer",
        }
        res_ovr = client.post(
            f"/api/rules/runs/{run_id}/teams/team_ineligible/override",
            json=override_payload,
        )
        assert res_ovr.status_code == 200
        assert res_ovr.json()["override_status"] == "ELIGIBLE"

        # Fetch run: override is merged and summary updated
        res_run_after = client.get(f"/api/rules/runs/{run_id}")
        assert res_run_after.status_code == 200
        merged = res_run_after.json()
        assert merged["teams"][0]["status"] == "ELIGIBLE"
        assert merged["teams"][0]["has_override"] is True
        assert merged["summary"]["eligible_count"] == 1
        assert merged["summary"]["ineligible_count"] == 0

    def test_override_requires_non_empty_reason(self):
        # Create a run first
        team = {"team_id": "t1", "team_name": "T", "members": [{"member_id": "m1", "name": "A"}]}
        run_res = client.post("/api/rules/evaluate", json={"teams": [team], "config_id": "basic"}).json()
        run_id = run_res["run_id"]

        # Attempt override with blank reason
        blank_ovr = {"override_status": "ELIGIBLE", "reason": "   "}
        res = client.post(f"/api/rules/runs/{run_id}/teams/t1/override", json=blank_ovr)
        assert res.status_code == 400


# ---------------------------------------------------------------------------
# 11. End-to-End API Evaluation Tests
# ---------------------------------------------------------------------------


class TestApiEvaluationCases:
    def test_api_produces_ineligible_team(self):
        """Team with 1 member under strict preset (min 2) is INELIGIBLE."""
        payload = {
            "teams": [
                {
                    "team_id": "t_ineligible",
                    "team_name": "Under-sized Team",
                    "members": [{"member_id": "m1", "name": "Alice", "github_url": "https://github.com/alice"}],
                }
            ],
            "config_id": "strict",
        }
        res = client.post("/api/rules/evaluate", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["teams"][0]["status"] == "INELIGIBLE"
        assert any("team size" in r.lower() for r in data["teams"][0]["reasons"])

    def test_api_produces_needs_review_team(self):
        """Team meeting size, but academic CGPA is missing/unavailable -> NEEDS_REVIEW."""
        payload = {
            "teams": [
                {
                    "team_id": "t_review",
                    "team_name": "Review Team",
                    "members": [
                        {"member_id": "m1", "name": "Alice", "github_url": "https://github.com/alice"},
                        {"member_id": "m2", "name": "Bob", "github_url": "https://github.com/bob"},
                    ],
                }
            ],
            "config_id": "strict",
        }
        res = client.post("/api/rules/evaluate", json=payload)
        assert res.status_code == 200
        data = res.json()
        # CGPA signal is absent from payload -> UNAVAILABLE -> manual_review -> NEEDS_REVIEW
        assert data["teams"][0]["status"] == "NEEDS_REVIEW"
        assert data["summary"]["needs_review_count"] == 1

    def test_api_produces_eligible_team(self):
        """Team satisfying all hard rules under basic preset is ELIGIBLE."""
        payload = {
            "teams": [
                {
                    "team_id": "t_eligible",
                    "team_name": "Full Squad",
                    "members": [
                        {"member_id": "m1", "name": "Alice", "github_url": "https://github.com/alice"},
                        {"member_id": "m2", "name": "Bob"},
                    ],
                }
            ],
            "config_id": "basic",
        }
        res = client.post("/api/rules/evaluate", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["teams"][0]["status"] == "ELIGIBLE"
        assert data["summary"]["eligible_count"] == 1
