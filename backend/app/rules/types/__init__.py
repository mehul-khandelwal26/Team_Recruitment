"""Rule type evaluator registry and catalog descriptors matching Prompt 4.1 specification.

Catalog exposes exactly the 10 specified rule types:
 1. team_size_min
 2. team_size_max
 3. required_link
 4. required_signal_present
 5. signal_threshold
 6. signal_contains
 7. allowed_values
 8. track_limit
 9. duplicate_member_email
 10. required_fields_present
"""

from __future__ import annotations

from typing import Optional

from app.rules.schemas import RuleScope, RuleSeverity, RuleTypeCatalogItem
from app.rules.types.allowed_values import AllowedValuesEvaluator
from app.rules.types.base import RuleEvaluatorBase
from app.rules.types.duplicate_member_email import DuplicateMemberEmailEvaluator
from app.rules.types.required_fields_present import RequiredFieldsPresentEvaluator
from app.rules.types.required_link import RequiredLinkEvaluator
from app.rules.types.required_signal_present import RequiredSignalPresentEvaluator
from app.rules.types.signal_contains import SignalContainsEvaluator
from app.rules.types.signal_threshold import SignalThresholdEvaluator
from app.rules.types.team_size_max import TeamSizeMaxEvaluator
from app.rules.types.team_size_min import TeamSizeMinEvaluator
from app.rules.types.track_limit import TrackLimitEvaluator

# Legacy imports for test backward-compatibility fallback
from app.rules.types.academic_year_range import AcademicYearRangeEvaluator
from app.rules.types.cgpa_minimum import CgpaMinimumEvaluator
from app.rules.types.custom_signal_threshold import CustomSignalThresholdEvaluator
from app.rules.types.github_repos_minimum import GithubReposMinimumEvaluator
from app.rules.types.normalized_cgpa_minimum import NormalizedCgpaMinimumEvaluator
from app.rules.types.team_size_range import TeamSizeRangeEvaluator

# The 10 official evaluators
RULE_EVALUATORS: dict[str, RuleEvaluatorBase] = {
    "team_size_min": TeamSizeMinEvaluator(),
    "team_size_max": TeamSizeMaxEvaluator(),
    "required_link": RequiredLinkEvaluator(),
    "required_signal_present": RequiredSignalPresentEvaluator(),
    "signal_threshold": SignalThresholdEvaluator(),
    "signal_contains": SignalContainsEvaluator(),
    "allowed_values": AllowedValuesEvaluator(),
    "track_limit": TrackLimitEvaluator(),
    "duplicate_member_email": DuplicateMemberEmailEvaluator(),
    "required_fields_present": RequiredFieldsPresentEvaluator(),
}

# Legacy evaluators preserved strictly for internal fallback compatibility with older tests
_LEGACY_EVALUATORS: dict[str, RuleEvaluatorBase] = {
    "team_size_range": TeamSizeRangeEvaluator(),
    "cgpa_minimum": CgpaMinimumEvaluator(),
    "normalized_cgpa_minimum": NormalizedCgpaMinimumEvaluator(),
    "github_repos_minimum": GithubReposMinimumEvaluator(),
    "academic_year_range": AcademicYearRangeEvaluator(),
    "custom_signal_threshold": CustomSignalThresholdEvaluator(),
}


def get_evaluator(rule_type: str) -> Optional[RuleEvaluatorBase]:
    """Retrieve an evaluator instance by rule type string.

    Prioritizes official 10 catalog types, with backward compatibility
    fallbacks for legacy test objects.
    """
    if rule_type in RULE_EVALUATORS:
        return RULE_EVALUATORS[rule_type]
    if rule_type in _LEGACY_EVALUATORS:
        return _LEGACY_EVALUATORS[rule_type]
    return None


# Exactly 10 catalog items
RULE_TYPE_CATALOG: list[RuleTypeCatalogItem] = [
    RuleTypeCatalogItem(
        rule_type="team_size_min",
        name="Minimum Team Size",
        description="Verifies that the team has at least min_size registered members.",
        scope="team",
        default_severity=RuleSeverity.HARD,
        supported_severities=[RuleSeverity.HARD, RuleSeverity.SOFT],
        supported_scopes=[RuleScope.TEAM, RuleScope.TEAM_LEVEL],
        required_parameters=["min_size"],
        optional_parameters=[],
        supported_operators=[],
        supported_member_selections=[],
        supported_aggregations=[],
        accepted_value_types=["integer"],
        missing_data_behavior="Empty team (0 members) fails if min_size > 0, passes if min_size == 0.",
        parameters_schema={
            "min_size": {"type": "integer", "minimum": 0, "description": "Minimum member count required."}
        },
    ),
    RuleTypeCatalogItem(
        rule_type="team_size_max",
        name="Maximum Team Size",
        description="Verifies that the team does not exceed max_size registered members.",
        scope="team",
        default_severity=RuleSeverity.HARD,
        supported_severities=[RuleSeverity.HARD, RuleSeverity.SOFT],
        supported_scopes=[RuleScope.TEAM, RuleScope.TEAM_LEVEL],
        required_parameters=["max_size"],
        optional_parameters=[],
        supported_operators=[],
        supported_member_selections=[],
        supported_aggregations=[],
        accepted_value_types=["integer"],
        missing_data_behavior="Team exceeding max_size fails; empty team (0 members) passes.",
        parameters_schema={
            "max_size": {"type": "integer", "minimum": 1, "description": "Maximum member count permitted."}
        },
    ),
    RuleTypeCatalogItem(
        rule_type="required_link",
        name="Required Link / Profile URL",
        description="Checks presence of essential candidate URLs (github_url, resume_url, linkedin_url, portfolio_url, or custom URL).",
        scope="member",
        default_severity=RuleSeverity.HARD,
        supported_severities=[RuleSeverity.HARD, RuleSeverity.SOFT],
        supported_scopes=[RuleScope.MEMBER, RuleScope.ALL_MEMBERS, RuleScope.ANY_MEMBER, RuleScope.TEAM_LEAD],
        required_parameters=["link_field"],
        optional_parameters=["link_type", "member_selection"],
        supported_operators=[],
        supported_member_selections=["all_members", "any_member", "team_lead"],
        supported_aggregations=[],
        accepted_value_types=["string"],
        missing_data_behavior="Collected but blank -> NOT PROVIDED (fails). Unmapped / uncollected -> UNAVAILABLE (on_missing applies).",
        parameters_schema={
            "link_field": {
                "type": "string",
                "default": "github_url",
                "description": "Field key in registration data or canonical attribute.",
            }
        },
    ),
    RuleTypeCatalogItem(
        rule_type="required_signal_present",
        name="Required Extracted Signal Presence",
        description="Ensures an evaluation signal has been extracted with a valid result (0 is valid).",
        scope="member",
        default_severity=RuleSeverity.HARD,
        supported_severities=[RuleSeverity.HARD, RuleSeverity.SOFT],
        supported_scopes=[RuleScope.MEMBER, RuleScope.ALL_MEMBERS, RuleScope.ANY_MEMBER, RuleScope.TEAM_LEAD],
        required_parameters=["signal_key"],
        optional_parameters=["member_selection"],
        supported_operators=[],
        supported_member_selections=["all_members", "any_member", "team_lead"],
        supported_aggregations=[],
        accepted_value_types=["any"],
        missing_data_behavior="EXTRACTED (including 0) -> PASSED. NOT_APPLICABLE -> NOT PROVIDED (fails). FAILED/absent payload -> UNAVAILABLE (on_missing).",
        parameters_schema={
            "signal_key": {"type": "string", "description": "Signal identifier to require, validated against registry."}
        },
    ),
    RuleTypeCatalogItem(
        rule_type="signal_threshold",
        name="Generic Signal Numeric Threshold",
        description="Compares an extracted numeric signal against a numeric threshold with configurable operator and aggregation.",
        scope="member",
        default_severity=RuleSeverity.HARD,
        supported_severities=[RuleSeverity.HARD, RuleSeverity.SOFT],
        supported_scopes=[RuleScope.MEMBER, RuleScope.ALL_MEMBERS, RuleScope.ANY_MEMBER, RuleScope.TEAM_LEAD],
        required_parameters=["signal_key", "operator", "threshold"],
        optional_parameters=["member_selection", "aggregation"],
        supported_operators=[">=", ">", "<=", "<", "==", "!="],
        supported_member_selections=["all_members", "any_member", "team_lead"],
        supported_aggregations=["all", "any", "min", "max", "mean"],
        accepted_value_types=["integer", "float", "numeric"],
        missing_data_behavior="Booleans, NaN, Inf, and missing members are UNAVAILABLE. Missing member is never silently dropped in min/max/mean (triggers on_missing). Legitimate 0 is valid.",
        parameters_schema={
            "signal_key": {"type": "string", "description": "Numeric signal identifier registered in default_signal_registry."},
            "operator": {"type": "string", "enum": [">=", ">", "<=", "<", "==", "!="], "default": ">="},
            "threshold": {"type": "number", "description": "Numeric cutoff value."},
            "member_selection": {"type": "string", "enum": ["all_members", "any_member", "team_lead"], "default": "all_members"},
            "aggregation": {"type": "string", "enum": ["all", "any", "min", "max", "mean"], "default": "all"},
        },
    ),
    RuleTypeCatalogItem(
        rule_type="signal_contains",
        name="Signal Contains Value",
        description="Checks whether an extracted list or dictionary signal contains an expected value (case-insensitive for strings).",
        scope="member",
        default_severity=RuleSeverity.HARD,
        supported_severities=[RuleSeverity.HARD, RuleSeverity.SOFT],
        supported_scopes=[RuleScope.MEMBER, RuleScope.ALL_MEMBERS, RuleScope.ANY_MEMBER, RuleScope.TEAM_LEAD],
        required_parameters=["signal_key", "expected_value"],
        optional_parameters=["dict_key", "member_selection"],
        supported_operators=[],
        supported_member_selections=["all_members", "any_member", "team_lead"],
        supported_aggregations=[],
        accepted_value_types=["list", "dict"],
        missing_data_behavior="Incompatible runtime type, unextracted or missing signal -> UNAVAILABLE. NOT_APPLICABLE -> NOT PROVIDED (fails).",
        parameters_schema={
            "signal_key": {"type": "string", "description": "List or dict signal identifier."},
            "expected_value": {"type": "string", "description": "Value or token to search for."},
            "dict_key": {"type": "string", "default": None, "description": "Optional dictionary key to inspect."},
            "member_selection": {"type": "string", "enum": ["all_members", "any_member", "team_lead"], "default": "any_member"},
        },
    ),
    RuleTypeCatalogItem(
        rule_type="allowed_values",
        name="Allowed Field or Signal Values",
        description="Verifies that a field or categorical signal contains one of the explicitly permitted values.",
        scope="member",
        default_severity=RuleSeverity.HARD,
        supported_severities=[RuleSeverity.HARD, RuleSeverity.SOFT],
        supported_scopes=[RuleScope.MEMBER, RuleScope.TEAM, RuleScope.ALL_MEMBERS, RuleScope.ANY_MEMBER, RuleScope.TEAM_LEAD],
        required_parameters=["allowed_values"],
        optional_parameters=["field_key", "signal_key", "member_selection"],
        supported_operators=[],
        supported_member_selections=["all_members", "any_member", "team_lead"],
        supported_aggregations=[],
        accepted_value_types=["string", "integer", "any"],
        missing_data_behavior="Collected blank or NOT_APPLICABLE -> NOT PROVIDED (fails). Unmapped / uncollected -> UNAVAILABLE (on_missing applies).",
        parameters_schema={
            "field_key": {"type": "string", "description": "Registration field key to check."},
            "signal_key": {"type": "string", "description": "Optional categorical signal key to check instead."},
            "allowed_values": {"type": "array", "items": "string", "description": "List of permitted values."},
            "member_selection": {"type": "string", "enum": ["all_members", "any_member", "team_lead"], "default": "all_members"},
        },
    ),
    RuleTypeCatalogItem(
        rule_type="track_limit",
        name="Track Capacity Limit",
        description="Enforces maximum team capacity limits per track across the submitted team set.",
        scope="cross_team",
        default_severity=RuleSeverity.HARD,
        supported_severities=[RuleSeverity.HARD, RuleSeverity.SOFT],
        supported_scopes=[RuleScope.CROSS_TEAM, RuleScope.TEAM],
        required_parameters=["field_key"],
        optional_parameters=["track_limits", "limit", "track"],
        supported_operators=[],
        supported_member_selections=[],
        supported_aggregations=[],
        accepted_value_types=["string", "integer"],
        missing_data_behavior="Absent or unmapped track field is UNAVAILABLE (never defaulted; on_missing applies).",
        parameters_schema={
            "field_key": {"type": "string", "description": "Field key representing the team's track."},
            "track_limits": {"type": "object", "description": "Dictionary mapping track names to integer limits."},
            "limit": {"type": "integer", "description": "Capacity limit if applying to a single track."},
            "track": {"type": "string", "description": "Track name if specifying limit directly."},
        },
    ),
    RuleTypeCatalogItem(
        rule_type="duplicate_member_email",
        name="Duplicate Member Email Across Teams",
        description="Cross-team check ensuring member emails are not registered across multiple distinct teams.",
        scope="cross_team",
        default_severity=RuleSeverity.HARD,
        supported_severities=[RuleSeverity.HARD, RuleSeverity.SOFT],
        supported_scopes=[RuleScope.CROSS_TEAM],
        required_parameters=[],
        optional_parameters=["email_field"],
        supported_operators=[],
        supported_member_selections=[],
        supported_aggregations=[],
        accepted_value_types=["string"],
        missing_data_behavior="Blank emails ignored. Same-team repeats ignored. Conflicting team IDs named in explanation. Deterministic across team ordering.",
        parameters_schema={
            "email_field": {"type": "string", "default": "email", "description": "Field key used for member email."}
        },
    ),
    RuleTypeCatalogItem(
        rule_type="required_fields_present",
        name="Required Registration Fields",
        description="Verifies that all designated registration form columns or custom attributes are populated.",
        scope="member",
        default_severity=RuleSeverity.HARD,
        supported_severities=[RuleSeverity.HARD, RuleSeverity.SOFT],
        supported_scopes=[RuleScope.MEMBER, RuleScope.ALL_MEMBERS, RuleScope.ANY_MEMBER, RuleScope.TEAM_LEAD],
        required_parameters=["field_keys"],
        optional_parameters=["member_selection"],
        supported_operators=[],
        supported_member_selections=["all_members", "any_member", "team_lead"],
        supported_aggregations=[],
        accepted_value_types=["string", "any"],
        missing_data_behavior="Collected blank -> NOT PROVIDED (fails). Unmapped / uncollected -> UNAVAILABLE (on_missing applies).",
        parameters_schema={
            "field_keys": {"type": "array", "items": "string", "description": "List of required field keys."}
        },
    ),
]
