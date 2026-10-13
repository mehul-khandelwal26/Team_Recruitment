"""Built-in rule configuration presets for hackathons and team recruitment.

Presets:
1. 'basic': Core team size (2-4), at least one GitHub URL (hard), and CGPA >= 6.0 (soft).
2. 'strict': Team size (2-4), all members have GitHub (hard), all members CGPA >= 7.0 (hard),
   any member has >= 1 repo (hard), and all members have resume link (soft).
3. 'open_solo': Permissive team size (1-4), at least one GitHub URL (hard), CGPA >= 6.0 (soft).

Condition 3 enforced:
No preset contains a hard rule that depends on resume signals.
"""

from __future__ import annotations

import datetime
from app.rules.schemas import (
    GlobalRuleConfig,
    OnMissingAction,
    RuleConfiguration,
    RuleDefinition,
    RuleScope,
    RuleSeverity,
)


def get_default_presets() -> list[RuleConfiguration]:
    """Generate the standard built-in configuration presets."""
    now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # 1. Basic Preset
    basic_preset = RuleConfiguration(
        config_id="basic",
        version=1,
        name="Basic Eligibility",
        description="Standard team sizing and basic technical profile requirements.",
        global_config=GlobalRuleConfig(lead_field="role"),
        rules=[
            RuleDefinition(
                rule_id="basic_team_size",
                rule_type="team_size_range",
                name="Team Size (2-4 Members)",
                description="Team must have between 2 and 4 registered members.",
                severity=RuleSeverity.HARD,
                scope=RuleScope.TEAM_LEVEL,
                is_enabled=True,
                order=1,
                on_missing=OnMissingAction.MANUAL_REVIEW,
                parameters={"min_size": 2, "max_size": 4},
            ),
            RuleDefinition(
                rule_id="basic_github_presence",
                rule_type="required_link",
                name="Technical Profile Link (Any Member)",
                description="At least one team member must provide a GitHub profile link.",
                severity=RuleSeverity.HARD,
                scope=RuleScope.ANY_MEMBER,
                is_enabled=True,
                order=2,
                on_missing=OnMissingAction.MANUAL_REVIEW,
                parameters={"link_type": "github_url"},
            ),
            RuleDefinition(
                rule_id="basic_academic_cgpa",
                rule_type="cgpa_minimum",
                name="Academic Standing (CGPA >= 6.0)",
                description="Members should maintain a minimum CGPA of 6.0.",
                severity=RuleSeverity.SOFT,  # Soft rule: provides signal without disqualifying
                scope=RuleScope.ALL_MEMBERS,
                is_enabled=True,
                order=3,
                on_missing=OnMissingAction.MANUAL_REVIEW,
                parameters={"min_cgpa": 6.0},
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
        name="Strict Hackathon Eligibility",
        description="Rigorous multi-member eligibility with high academic and technical bars.",
        global_config=GlobalRuleConfig(lead_field="role"),
        rules=[
            RuleDefinition(
                rule_id="strict_team_size",
                rule_type="team_size_range",
                name="Team Size (2-4 Members)",
                description="Team must have between 2 and 4 registered members.",
                severity=RuleSeverity.HARD,
                scope=RuleScope.TEAM_LEVEL,
                is_enabled=True,
                order=1,
                on_missing=OnMissingAction.FAIL,
                parameters={"min_size": 2, "max_size": 4},
            ),
            RuleDefinition(
                rule_id="strict_all_github",
                rule_type="required_link",
                name="GitHub Required for All Members",
                description="Every team member must provide a valid GitHub profile URL.",
                severity=RuleSeverity.HARD,
                scope=RuleScope.ALL_MEMBERS,
                is_enabled=True,
                order=2,
                on_missing=OnMissingAction.FAIL,
                parameters={"link_type": "github_url"},
            ),
            RuleDefinition(
                rule_id="strict_cgpa_min",
                rule_type="cgpa_minimum",
                name="High Academic Bar (CGPA >= 7.0)",
                description="All members must have a CGPA of at least 7.0.",
                severity=RuleSeverity.HARD,
                scope=RuleScope.ALL_MEMBERS,
                is_enabled=True,
                order=3,
                on_missing=OnMissingAction.MANUAL_REVIEW,
                parameters={"min_cgpa": 7.0},
            ),
            RuleDefinition(
                rule_id="strict_github_activity",
                rule_type="github_repos_minimum",
                name="Active Codebase (>= 1 Public Repo)",
                description="At least one team member must have at least 1 public repository.",
                severity=RuleSeverity.HARD,
                scope=RuleScope.ANY_MEMBER,
                is_enabled=True,
                order=4,
                on_missing=OnMissingAction.MANUAL_REVIEW,
                parameters={"min_repos": 1},
            ),
            RuleDefinition(
                rule_id="strict_resume_check",
                rule_type="required_link",
                name="Resume Submission Check",
                description="All members are encouraged to submit a resume.",
                severity=RuleSeverity.SOFT,  # Soft rule per Condition 3
                scope=RuleScope.ALL_MEMBERS,
                is_enabled=True,
                order=5,
                on_missing=OnMissingAction.MANUAL_REVIEW,
                parameters={"link_type": "resume_url"},
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
        name="Open to Solos and Teams",
        description="Accommodates individual solo participants alongside teams of up to 4.",
        global_config=GlobalRuleConfig(lead_field="role"),
        rules=[
            RuleDefinition(
                rule_id="solo_team_size",
                rule_type="team_size_range",
                name="Solo or Team (1-4 Members)",
                description="Allows solo participants (1 member) up to teams of 4 members.",
                severity=RuleSeverity.HARD,
                scope=RuleScope.TEAM_LEVEL,
                is_enabled=True,
                order=1,
                on_missing=OnMissingAction.MANUAL_REVIEW,
                parameters={"min_size": 1, "max_size": 4},
            ),
            RuleDefinition(
                rule_id="solo_github_presence",
                rule_type="required_link",
                name="Technical Profile Link",
                description="At least one member must provide a GitHub profile link.",
                severity=RuleSeverity.HARD,
                scope=RuleScope.ANY_MEMBER,
                is_enabled=True,
                order=2,
                on_missing=OnMissingAction.MANUAL_REVIEW,
                parameters={"link_type": "github_url"},
            ),
            RuleDefinition(
                rule_id="solo_cgpa_check",
                rule_type="cgpa_minimum",
                name="Academic Recommendation (CGPA >= 6.0)",
                description="At least one member should meet academic baseline.",
                severity=RuleSeverity.SOFT,  # Soft rule
                scope=RuleScope.ANY_MEMBER,
                is_enabled=True,
                order=3,
                on_missing=OnMissingAction.MANUAL_REVIEW,
                parameters={"min_cgpa": 6.0},
            ),
        ],
        is_active=True,
        created_at=now_ts,
        updated_at=now_ts,
    )

    return [basic_preset, strict_preset, open_solo_preset]
