"""Rule type evaluator registry and catalog descriptors.

Registers all 10 eligibility rule evaluators:
1. team_size_range
2. required_link
3. required_fields_present
4. required_signal_present
5. cgpa_minimum
6. normalized_cgpa_minimum
7. github_repos_minimum
8. academic_year_range
9. allowed_values
10. custom_signal_threshold
"""

from __future__ import annotations

from typing import Optional

from app.rules.schemas import RuleScope, RuleSeverity, RuleTypeCatalogItem
from app.rules.types.academic_year_range import AcademicYearRangeEvaluator
from app.rules.types.allowed_values import AllowedValuesEvaluator
from app.rules.types.base import RuleEvaluatorBase
from app.rules.types.cgpa_minimum import CgpaMinimumEvaluator
from app.rules.types.custom_signal_threshold import CustomSignalThresholdEvaluator
from app.rules.types.github_repos_minimum import GithubReposMinimumEvaluator
from app.rules.types.normalized_cgpa_minimum import NormalizedCgpaMinimumEvaluator
from app.rules.types.required_fields_present import RequiredFieldsPresentEvaluator
from app.rules.types.required_link import RequiredLinkEvaluator
from app.rules.types.required_signal_present import RequiredSignalPresentEvaluator
from app.rules.types.team_size_range import TeamSizeRangeEvaluator

# Instances registry
RULE_EVALUATORS: dict[str, RuleEvaluatorBase] = {
    "team_size_range": TeamSizeRangeEvaluator(),
    "required_link": RequiredLinkEvaluator(),
    "required_fields_present": RequiredFieldsPresentEvaluator(),
    "required_signal_present": RequiredSignalPresentEvaluator(),
    "cgpa_minimum": CgpaMinimumEvaluator(),
    "normalized_cgpa_minimum": NormalizedCgpaMinimumEvaluator(),
    "github_repos_minimum": GithubReposMinimumEvaluator(),
    "academic_year_range": AcademicYearRangeEvaluator(),
    "allowed_values": AllowedValuesEvaluator(),
    "custom_signal_threshold": CustomSignalThresholdEvaluator(),
}


def get_evaluator(rule_type: str) -> Optional[RuleEvaluatorBase]:
    """Retrieve an evaluator instance by rule type string."""
    return RULE_EVALUATORS.get(rule_type)


RULE_TYPE_CATALOG: list[RuleTypeCatalogItem] = [
    RuleTypeCatalogItem(
        rule_type="team_size_range",
        name="Team Size Constraint",
        description="Verifies that the number of members on a team is within [min_size, max_size].",
        default_severity=RuleSeverity.HARD,
        supported_scopes=[RuleScope.TEAM_LEVEL],
        parameters_schema={
            "min_size": {"type": "integer", "default": 1, "description": "Minimum member count required."},
            "max_size": {"type": "integer", "default": None, "description": "Maximum member count permitted."},
        },
    ),
    RuleTypeCatalogItem(
        rule_type="required_link",
        name="Required Link / Profile URL",
        description="Checks presence of essential candidate URLs (github_url, resume_url, linkedin_url, portfolio_url).",
        default_severity=RuleSeverity.HARD,
        supported_scopes=[RuleScope.ALL_MEMBERS, RuleScope.ANY_MEMBER, RuleScope.TEAM_LEAD],
        parameters_schema={
            "link_type": {
                "type": "string",
                "default": "github_url",
                "enum": ["github_url", "resume_url", "linkedin_url", "portfolio_url"],
            }
        },
    ),
    RuleTypeCatalogItem(
        rule_type="required_fields_present",
        name="Required Registration Fields",
        description="Verifies that mandatory registration form columns or custom attributes are populated.",
        default_severity=RuleSeverity.HARD,
        supported_scopes=[RuleScope.ALL_MEMBERS, RuleScope.ANY_MEMBER, RuleScope.TEAM_LEAD],
        parameters_schema={
            "field_keys": {"type": "array", "items": "string", "description": "List of required field keys."}
        },
    ),
    RuleTypeCatalogItem(
        rule_type="required_signal_present",
        name="Required Extracted Signal Presence",
        description="Ensures an evaluation signal has been extracted with a valid result.",
        default_severity=RuleSeverity.HARD,
        supported_scopes=[RuleScope.ALL_MEMBERS, RuleScope.ANY_MEMBER, RuleScope.TEAM_LEAD],
        parameters_schema={
            "signal_key": {"type": "string", "description": "Signal identifier to require."}
        },
    ),
    RuleTypeCatalogItem(
        rule_type="cgpa_minimum",
        name="Minimum Academic CGPA / CPI",
        description="Enforces a minimum candidate CGPA/CPI on its original scale.",
        default_severity=RuleSeverity.HARD,
        supported_scopes=[RuleScope.ALL_MEMBERS, RuleScope.ANY_MEMBER, RuleScope.TEAM_LEAD],
        parameters_schema={
            "min_cgpa": {"type": "number", "default": 6.0, "description": "Minimum acceptable score."}
        },
    ),
    RuleTypeCatalogItem(
        rule_type="normalized_cgpa_minimum",
        name="Minimum Normalized CGPA (10-Scale)",
        description="Enforces a minimum candidate CGPA normalized onto a standard 10-point scale.",
        default_severity=RuleSeverity.HARD,
        supported_scopes=[RuleScope.ALL_MEMBERS, RuleScope.ANY_MEMBER, RuleScope.TEAM_LEAD],
        parameters_schema={
            "min_cgpa": {"type": "number", "default": 7.0, "description": "Minimum acceptable score on 10-point scale."}
        },
    ),
    RuleTypeCatalogItem(
        rule_type="github_repos_minimum",
        name="Minimum Public GitHub Repositories",
        description="Checks that candidates maintain at least the required number of public GitHub repositories.",
        default_severity=RuleSeverity.HARD,
        supported_scopes=[RuleScope.ALL_MEMBERS, RuleScope.ANY_MEMBER, RuleScope.TEAM_LEAD],
        parameters_schema={
            "min_repos": {"type": "integer", "default": 1, "description": "Minimum public repositories."}
        },
    ),
    RuleTypeCatalogItem(
        rule_type="academic_year_range",
        name="Academic Year / Batch Requirement",
        description="Restricts eligibility to specific academic standings or graduation batches.",
        default_severity=RuleSeverity.HARD,
        supported_scopes=[RuleScope.ALL_MEMBERS, RuleScope.ANY_MEMBER, RuleScope.TEAM_LEAD],
        parameters_schema={
            "allowed_years": {
                "type": "array",
                "items": "string",
                "default": ["2nd Year", "3rd Year", "4th Year"],
            }
        },
    ),
    RuleTypeCatalogItem(
        rule_type="allowed_values",
        name="Allowed Field Values (Track / Branch)",
        description="Restricts values of a custom or canonical field (such as track, branch, or department).",
        default_severity=RuleSeverity.HARD,
        supported_scopes=[RuleScope.ALL_MEMBERS, RuleScope.ANY_MEMBER, RuleScope.TEAM_LEAD],
        parameters_schema={
            "field_key": {"type": "string", "description": "Designated field to inspect."},
            "allowed_values": {"type": "array", "items": "string", "description": "Permitted values list."},
        },
    ),
    RuleTypeCatalogItem(
        rule_type="custom_signal_threshold",
        name="Custom Signal Numeric Threshold",
        description="Applies comparison operator against an arbitrary numeric signal with strict NaN/bool rejection.",
        default_severity=RuleSeverity.HARD,
        supported_scopes=[RuleScope.ALL_MEMBERS, RuleScope.ANY_MEMBER, RuleScope.TEAM_LEAD],
        parameters_schema={
            "signal_key": {"type": "string", "description": "Signal identifier to evaluate."},
            "threshold": {"type": "number", "description": "Numeric cutoff value."},
            "operator": {"type": "string", "enum": [">=", "<=", ">", "<", "=="], "default": ">="},
        },
    ),
]
