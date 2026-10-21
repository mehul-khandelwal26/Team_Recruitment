"""Built-in rule configuration presets for hackathons and team recruitment.

Presets:
1. 'basic': Standard sizing (2-4 members), at least one GitHub URL (hard), and CGPA >= 6.0 advisory (soft).
2. 'strict': Rigorous sizing (2-4 members), all members have GitHub (hard), all members CGPA >= 7.0 (hard),
   any member has >= 1 public repo (hard), and all members have resume link (soft).
3. 'open_solo': Permissive sizing (1-4 members), at least one GitHub URL (hard), CGPA >= 6.0 advisory (soft).

Condition 3 enforced:
No preset contains a hard rule that depends on resume-derived signals.
"""

from __future__ import annotations

import datetime

from app.rules.schemas import (
    AggregationMethod,
    GlobalRuleConfig,
    MemberSelection,
    OnMissingAction,
    RuleConfiguration,
    RuleDefinition,
    RuleScope,
    RuleSeverity,
)


def get_default_presets() -> list[RuleConfiguration]:
    """Generate the standard built-in configuration presets using generic rule types."""
    now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # 1. Basic Preset
    basic_preset = RuleConfiguration(
        config_id="basic",
        version=1,
        user_id="system",
        name="Basic Eligibility",
        description="Standard team sizing and basic technical profile requirements.",
        global_config=GlobalRuleConfig(lead_field="role"),
        rules=[
            RuleDefinition(
                rule_id="basic_team_size_min",
                rule_type="team_size_min",
                name="Minimum Team Size (>= 2 Members)",
                description="Team must have at least 2 registered members.",
                severity=RuleSeverity.HARD,
                scope=RuleScope.TEAM,
                is_enabled=True,
                order=1,
                on_missing=OnMissingAction.MANUAL_REVIEW,
                parameters={"min_size": 2},
            ),
            RuleDefinition(
                rule_id="basic_team_size_max",
                rule_type="team_size_max",
                name="Maximum Team Size (<= 4 Members)",
                description="Team must have no more than 4 registered members.",
                severity=RuleSeverity.HARD,
                scope=RuleScope.TEAM,
                is_enabled=True,
                order=2,
                on_missing=OnMissingAction.MANUAL_REVIEW,
                parameters={"max_size": 4},
            ),
            RuleDefinition(
                rule_id="basic_github_presence",
                rule_type="required_link",
                name="Technical Profile Link (Any Member)",
                description="At least one team member must provide a GitHub profile link.",
                severity=RuleSeverity.HARD,
                scope=RuleScope.MEMBER,
                member_selection=MemberSelection.ANY_MEMBER,
                is_enabled=True,
                order=3,
                on_missing=OnMissingAction.MANUAL_REVIEW,
                parameters={"link_field": "github_url", "member_selection": "any_member"},
            ),
            RuleDefinition(
                rule_id="basic_academic_cgpa",
                rule_type="signal_threshold",
                name="Academic Standing (CGPA >= 6.0)",
                description="Members should maintain a minimum CGPA of 6.0.",
                severity=RuleSeverity.SOFT,  # Soft advisory rule
                scope=RuleScope.MEMBER,
                member_selection=MemberSelection.ALL_MEMBERS,
                aggregation=AggregationMethod.ALL,
                is_enabled=True,
                order=4,
                on_missing=OnMissingAction.MANUAL_REVIEW,
                parameters={
                    "signal_key": "academic_cgpa",
                    "operator": ">=",
                    "threshold": 6.0,
                    "member_selection": "all_members",
                    "aggregation": "all",
                },
            ),
        ],
        is_active=True,
        created_at=now_ts,
        updated_at=now_ts,
    )

    # 2. Strict Preset
    strict_preset = RuleConfiguration(
        config_id="strict",
        version=1,
        user_id="system",
        name="Strict Hackathon Eligibility",
        description="Rigorous multi-member eligibility with high academic and technical bars.",
        global_config=GlobalRuleConfig(lead_field="role"),
        rules=[
            RuleDefinition(
                rule_id="strict_team_size_min",
                rule_type="team_size_min",
                name="Minimum Team Size (>= 2 Members)",
                description="Team must have at least 2 registered members.",
                severity=RuleSeverity.HARD,
                scope=RuleScope.TEAM,
                is_enabled=True,
                order=1,
                on_missing=OnMissingAction.FAIL,
                parameters={"min_size": 2},
            ),
            RuleDefinition(
                rule_id="strict_team_size_max",
                rule_type="team_size_max",
                name="Maximum Team Size (<= 4 Members)",
                description="Team must have no more than 4 registered members.",
                severity=RuleSeverity.HARD,
                scope=RuleScope.TEAM,
                is_enabled=True,
                order=2,
                on_missing=OnMissingAction.FAIL,
                parameters={"max_size": 4},
            ),
            RuleDefinition(
                rule_id="strict_all_github",
                rule_type="required_link",
                name="GitHub Required for All Members",
                description="Every team member must provide a valid GitHub profile URL.",
                severity=RuleSeverity.HARD,
                scope=RuleScope.MEMBER,
                member_selection=MemberSelection.ALL_MEMBERS,
                is_enabled=True,
                order=3,
                on_missing=OnMissingAction.FAIL,
                parameters={"link_field": "github_url", "member_selection": "all_members"},
            ),
            RuleDefinition(
                rule_id="strict_cgpa_min",
                rule_type="signal_threshold",
                name="High Academic Bar (CGPA >= 7.0)",
                description="All members must have an academic CGPA of at least 7.0.",
                severity=RuleSeverity.HARD,
                scope=RuleScope.MEMBER,
                member_selection=MemberSelection.ALL_MEMBERS,
                aggregation=AggregationMethod.ALL,
                is_enabled=True,
                order=4,
                on_missing=OnMissingAction.MANUAL_REVIEW,
                parameters={
                    "signal_key": "academic_cgpa",
                    "operator": ">=",
                    "threshold": 7.0,
                    "member_selection": "all_members",
                    "aggregation": "all",
                },
            ),
            RuleDefinition(
                rule_id="strict_github_activity",
                rule_type="signal_threshold",
                name="Active Codebase (>= 1 Public Repo)",
                description="At least one team member must have at least 1 public repository.",
                severity=RuleSeverity.HARD,
                scope=RuleScope.MEMBER,
                member_selection=MemberSelection.ANY_MEMBER,
                aggregation=AggregationMethod.ANY,
                is_enabled=True,
                order=5,
                on_missing=OnMissingAction.MANUAL_REVIEW,
                parameters={
                    "signal_key": "github_public_repo_count",
                    "operator": ">=",
                    "threshold": 1,
                    "member_selection": "any_member",
                    "aggregation": "any",
                },
            ),
            RuleDefinition(
                rule_id="strict_resume_check",
                rule_type="required_link",
                name="Resume Submission Check",
                description="All members are encouraged to submit a resume link.",
                severity=RuleSeverity.SOFT,  # Soft advisory rule
                scope=RuleScope.MEMBER,
                member_selection=MemberSelection.ALL_MEMBERS,
                is_enabled=True,
                order=6,
                on_missing=OnMissingAction.MANUAL_REVIEW,
                parameters={"link_field": "resume_url", "member_selection": "all_members"},
            ),
        ],
        is_active=True,
        created_at=now_ts,
        updated_at=now_ts,
    )

    # 3. Open to Solos Preset
    open_solo_preset = RuleConfiguration(
        config_id="open_solo",
        version=1,
        user_id="system",
        name="Open to Solos and Teams",
        description="Accommodates individual solo participants alongside teams of up to 4.",
        global_config=GlobalRuleConfig(lead_field="role"),
        rules=[
            RuleDefinition(
                rule_id="solo_team_size_min",
                rule_type="team_size_min",
                name="Solo or Team (>= 1 Member)",
                description="Allows solo participants (1 member) or larger squads.",
                severity=RuleSeverity.HARD,
                scope=RuleScope.TEAM,
                is_enabled=True,
                order=1,
                on_missing=OnMissingAction.MANUAL_REVIEW,
                parameters={"min_size": 1},
            ),
            RuleDefinition(
                rule_id="solo_team_size_max",
                rule_type="team_size_max",
                name="Maximum Team Size (<= 4 Members)",
                description="Teams may have at most 4 members.",
                severity=RuleSeverity.HARD,
                scope=RuleScope.TEAM,
                is_enabled=True,
                order=2,
                on_missing=OnMissingAction.MANUAL_REVIEW,
                parameters={"max_size": 4},
            ),
            RuleDefinition(
                rule_id="solo_github_presence",
                rule_type="required_link",
                name="Technical Profile Link",
                description="At least one member must provide a GitHub profile link.",
                severity=RuleSeverity.HARD,
                scope=RuleScope.MEMBER,
                member_selection=MemberSelection.ANY_MEMBER,
                is_enabled=True,
                order=3,
                on_missing=OnMissingAction.MANUAL_REVIEW,
                parameters={"link_field": "github_url", "member_selection": "any_member"},
            ),
            RuleDefinition(
                rule_id="solo_cgpa_check",
                rule_type="signal_threshold",
                name="Academic Recommendation (CGPA >= 6.0)",
                description="At least one member should meet academic baseline.",
                severity=RuleSeverity.SOFT,  # Soft advisory rule
                scope=RuleScope.MEMBER,
                member_selection=MemberSelection.ANY_MEMBER,
                aggregation=AggregationMethod.ANY,
                is_enabled=True,
                order=4,
                on_missing=OnMissingAction.MANUAL_REVIEW,
                parameters={
                    "signal_key": "academic_cgpa",
                    "operator": ">=",
                    "threshold": 6.0,
                    "member_selection": "any_member",
                    "aggregation": "any",
                },
            ),
        ],
        is_active=True,
        created_at=now_ts,
        updated_at=now_ts,
    )

    # 4. Demo: Lead Academic Review Preset
    demo_mixed_review_preset = RuleConfiguration(
        config_id="demo_mixed_review",
        version=1,
        user_id="system",
        name="Demo: Lead Academic Review",
        description="Demo preset requiring team lead academic verification (CGPA >= 7.0) with manual review fallback.",
        global_config=GlobalRuleConfig(lead_field="role"),
        rules=[
            RuleDefinition(
                rule_id="min_size",
                rule_type="team_size_min",
                name="Minimum Team Size (>= 2 Members)",
                description="Team must have at least 2 registered members.",
                severity=RuleSeverity.HARD,
                scope=RuleScope.TEAM,
                is_enabled=True,
                order=1,
                parameters={"min_size": 2},
            ),
            RuleDefinition(
                rule_id="github_req",
                rule_type="required_link",
                name="Technical Profile Link (Any Member)",
                description="At least one team member must provide a GitHub profile link.",
                severity=RuleSeverity.HARD,
                scope=RuleScope.MEMBER,
                member_selection=MemberSelection.ANY_MEMBER,
                is_enabled=True,
                order=2,
                parameters={"link_field": "github_url", "member_selection": "any_member"},
            ),
            RuleDefinition(
                rule_id="lead_cgpa",
                rule_type="signal_threshold",
                name="Team Lead Academic Standing (CGPA >= 7.0)",
                description="Designated team lead must meet minimum academic CGPA of 7.0.",
                severity=RuleSeverity.HARD,
                scope=RuleScope.MEMBER,
                member_selection=MemberSelection.TEAM_LEAD,
                is_enabled=True,
                order=3,
                on_missing=OnMissingAction.MANUAL_REVIEW,
                parameters={
                    "signal_key": "academic_cgpa",
                    "operator": ">=",
                    "threshold": 7.0,
                    "member_selection": "team_lead",
                },
            ),
        ],
        is_active=True,
        created_at=now_ts,
        updated_at=now_ts,
    )

    return [basic_preset, strict_preset, open_solo_preset, demo_mixed_review_preset]

