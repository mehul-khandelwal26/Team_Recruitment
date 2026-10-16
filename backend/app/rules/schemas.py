"""Pydantic schemas for the deterministic eligibility rules engine.

Defines schemas for:
- Rule definitions, scopes, severity, and on_missing actions
- Configuration versioning and global configuration
- Rule evaluation results and team eligibility results
- In-memory run summaries and manual overrides
- Request and response models for the evaluation API
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EligibilityStatus(str, Enum):
    """Overall eligibility status of a team."""

    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class RuleResultStatus(str, Enum):
    """Outcome status of an individual rule evaluation."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


class RuleSeverity(str, Enum):
    """Severity level of a rule. Only HARD rules impact team eligibility."""

    HARD = "hard"
    SOFT = "soft"


class OnMissingAction(str, Enum):
    """Action to take when required data is UNAVAILABLE."""

    MANUAL_REVIEW = "manual_review"
    FAIL = "fail"
    PASS = "pass"
    SKIP = "skip"


class RuleScope(str, Enum):
    """Target evaluation scope for a rule."""

    MEMBER = "member"
    TEAM = "team"
    CROSS_TEAM = "cross_team"

    # Legacy aliases preserved for backward compatibility with existing tests
    ALL_MEMBERS = "all_members"
    ANY_MEMBER = "any_member"
    TEAM_LEVEL = "team_level"
    TEAM_LEAD = "team_lead"


class MemberSelection(str, Enum):
    """Member selection method within member scope."""

    ALL_MEMBERS = "all_members"
    ANY_MEMBER = "any_member"
    TEAM_LEAD = "team_lead"


class AggregationMethod(str, Enum):
    """Aggregation strategy across member values."""

    ALL = "all"
    ANY = "any"
    MIN = "min"
    MAX = "max"
    MEAN = "mean"


# ---------------------------------------------------------------------------
# Configuration Models
# ---------------------------------------------------------------------------


class GlobalRuleConfig(BaseModel):
    """Global configuration settings for a versioned rule set.

    Controls cross-cutting behaviors like which field indicates team lead status.
    """

    lead_field: str = Field(
        default="role",
        description="Field key in custom_fields or raw_data used to identify team lead.",
    )
    lead_values: list[str] = Field(
        default_factory=lambda: ["lead", "team lead", "captain", "leader", "team_lead"],
        description="Values in lead_field that indicate team lead status (case-insensitive).",
    )
    default_academic_scale: Optional[float] = Field(
        default=10.0,
        description="Default academic scale (e.g. 10.0) when not specified in signals.",
    )
    extra_mappings: dict[str, str] = Field(
        default_factory=dict,
        description="Optional alias mappings (original_key -> canonical_key).",
    )


class RuleDefinition(BaseModel):
    """Definition of an individual eligibility rule within a configuration."""

    rule_id: str = Field(..., description="Unique rule identifier within configuration.")
    rule_type: str = Field(..., description="Type of rule (e.g. 'required_link', 'signal_threshold').")
    name: str = Field(..., description="Human-readable rule name.")
    description: str = Field(default="", description="Detailed description of what this rule verifies.")
    severity: RuleSeverity = Field(
        default=RuleSeverity.HARD,
        description="Severity: 'hard' impacts team eligibility; 'soft' records results only.",
    )
    scope: RuleScope = Field(
        default=RuleScope.TEAM,
        description="Evaluation scope: 'member', 'team', or 'cross_team'.",
    )
    member_selection: Optional[MemberSelection] = Field(
        default=None,
        description="Member selection: 'all_members', 'any_member', 'team_lead'.",
    )
    aggregation: Optional[AggregationMethod] = Field(
        default=None,
        description="Aggregation method: 'all', 'any', 'min', 'max', 'mean'.",
    )
    is_enabled: bool = Field(default=True, description="Whether this rule is active.")
    order: int = Field(default=0, description="Evaluation order index (lower executes first).")
    on_missing: OnMissingAction = Field(
        default=OnMissingAction.MANUAL_REVIEW,
        description="Action to take if required data is UNAVAILABLE (cannot be determined).",
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Rule-specific configuration parameters.",
    )


class RuleConfiguration(BaseModel):
    """An immutable, versioned configuration containing a set of rules."""

    config_id: str = Field(..., description="Unique configuration identifier.")
    version: int = Field(default=1, description="Version number of this configuration (increments on edit).")
    name: str = Field(..., description="Human-readable name for this configuration.")
    description: str = Field(default="", description="Description of the configuration's purpose.")
    global_config: GlobalRuleConfig = Field(
        default_factory=GlobalRuleConfig,
        description="Global settings including lead_field.",
    )
    rules: list[RuleDefinition] = Field(
        default_factory=list,
        description="Ordered list of eligibility rules.",
    )
    is_active: bool = Field(default=True, description="Whether this configuration is currently active.")
    created_at: str = Field(default="", description="ISO timestamp of creation.")
    updated_at: str = Field(default="", description="ISO timestamp of last update/version creation.")


class RuleConfigurationCreate(BaseModel):
    """Payload to create a new rule configuration."""

    config_id: Optional[str] = Field(None, description="Optional custom ID; generated if omitted.")
    name: str = Field(..., description="Configuration display name.")
    description: str = Field(default="", description="Description of configuration.")
    global_config: GlobalRuleConfig = Field(default_factory=GlobalRuleConfig)
    rules: list[RuleDefinition] = Field(default_factory=list)


class RuleConfigurationUpdate(BaseModel):
    """Payload to update a rule configuration (creates a new version)."""

    name: Optional[str] = None
    description: Optional[str] = None
    global_config: Optional[GlobalRuleConfig] = None
    rules: Optional[list[RuleDefinition]] = None
    is_active: Optional[bool] = None


# ---------------------------------------------------------------------------
# Evaluation Results Models
# ---------------------------------------------------------------------------


class RuleResult(BaseModel):
    """Outcome of evaluating a single rule against a team."""

    rule_id: str = Field(..., description="ID of the evaluated rule.")
    rule_type: str = Field(..., description="Type of the evaluated rule.")
    name: str = Field(..., description="Display name of the rule.")
    severity: RuleSeverity = Field(..., description="Severity of the rule.")
    scope: RuleScope = Field(..., description="Evaluation scope.")
    status: RuleResultStatus = Field(..., description="Outcome status.")
    explanation: str = Field(..., description="Human-readable explanation of the result.")
    is_evaluable: bool = Field(
        default=True,
        description="True if rule had sufficient data to evaluate, False if data was UNAVAILABLE.",
    )
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured diagnostics and values checked.",
    )
    member_evaluations: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Per-member breakdown when scope is member-based.",
    )


class ManualOverride(BaseModel):
    """Record of an organizer's manual eligibility override for a team."""

    override_id: str = Field(..., description="Unique override identifier.")
    run_id: str = Field(..., description="Evaluation run ID where override applies.")
    team_id: str = Field(..., description="Team ID whose eligibility is overridden.")
    original_status: EligibilityStatus = Field(..., description="Original calculated status.")
    override_status: EligibilityStatus = Field(..., description="New manual status.")
    reason: str = Field(..., min_length=1, description="Required justification for override.")
    overridden_by: str = Field(default="organizer", description="Identifier of the reviewer.")
    overridden_at: str = Field(..., description="ISO timestamp of the override.")


class ManualOverrideCreate(BaseModel):
    """Request payload to apply a manual override."""

    override_status: EligibilityStatus = Field(..., description="New eligibility status.")
    reason: str = Field(..., min_length=1, description="Mandatory non-empty explanation.")
    overridden_by: Optional[str] = Field(default="organizer", description="Reviewer name or identifier.")


class TeamEligibilityResult(BaseModel):
    """Complete eligibility decision and audit trail for a single team."""

    team_id: str = Field(..., description="Team identifier.")
    team_name: str = Field(..., description="Team display name.")
    status: EligibilityStatus = Field(..., description="Final eligibility decision.")
    reasons: list[str] = Field(
        default_factory=list,
        description="Human-readable explanations for non-eligible or review status.",
    )
    rule_results: list[RuleResult] = Field(
        default_factory=list,
        description="Detailed results for each rule evaluated.",
    )
    data_completeness: Optional[float] = Field(
        default=None,
        description="Ratio of evaluable applicable rules to total applicable rules (None if 0 applicable).",
    )
    is_temporary_id: bool = Field(
        default=False,
        description="Whether team has an unresolved temporary ID.",
    )
    is_unresolved: bool = Field(
        default=False,
        description="Whether team identity is unresolved due to duplicate names.",
    )
    has_override: bool = Field(
        default=False,
        description="Whether a manual override has been applied to this team.",
    )
    override: Optional[ManualOverride] = Field(
        default=None,
        description="Override details if applied.",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Structural or execution errors encountered for this team.",
    )


# ---------------------------------------------------------------------------
# API Run and Request/Response Models
# ---------------------------------------------------------------------------


class EligibilityRunSummary(BaseModel):
    """Aggregate summary statistics for an eligibility run."""

    total_teams: int = 0
    eligible_count: int = 0
    ineligible_count: int = 0
    needs_review_count: int = 0
    error_count: int = 0


class MemberSignals(BaseModel):
    """Signals associated with a single team member."""

    member_id: str = Field(..., description="Member ID matching TeamSchema member_id.")
    signals: list[Any] = Field(
        default_factory=list,
        description="List of ExtractedSignal objects or signal dicts for this member.",
    )


class EligibilityEvaluateRequest(BaseModel):
    """Request to evaluate teams against a versioned eligibility configuration."""

    teams: list[Any] = Field(
        ...,
        description="List of TeamSchema objects or team dicts (from ingestion).",
    )
    signals: list[MemberSignals] = Field(
        default_factory=list,
        description="Optional pre-extracted signals per member. Evaluator never calls analyzers.",
    )
    config_id: Optional[str] = Field(
        default=None,
        description="Rule configuration ID to execute. Defaults to 'basic' preset.",
    )
    config_version: Optional[int] = Field(
        default=None,
        description="Optional specific version of the config. If omitted, uses latest version.",
    )
    evaluated_at: Optional[str] = Field(
        default=None,
        description="Optional ISO timestamp injected for deterministic evaluations.",
    )


class EligibilityRunResponse(BaseModel):
    """Standard response returned by the eligibility evaluation endpoint."""

    run_id: str = Field(..., description="Unique evaluation run identifier.")
    config_id: str = Field(..., description="Configuration ID used for evaluation.")
    config_version: int = Field(..., description="Configuration version used.")
    evaluated_at: str = Field(..., description="ISO timestamp of evaluation.")
    teams: list[TeamEligibilityResult] = Field(
        default_factory=list,
        description="Evaluated teams sorted by team_id.",
    )
    summary: EligibilityRunSummary = Field(
        default_factory=EligibilityRunSummary,
        description="Aggregate summary counts.",
    )
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    dataset_id: Optional[str] = Field(
        default=None,
        description="Optional dataset identifier if evaluated against a stored dataset snapshot.",
    )
    extraction_run_id: Optional[str] = Field(
        default=None,
        description="Optional extraction run identifier if signals were loaded from a stored extraction run.",
    )


class RuleTypeCatalogItem(BaseModel):
    """Catalog descriptor for an available rule type."""

    rule_type: str
    name: str
    description: str
    scope: str = Field(..., description="Evaluation scope: 'member', 'team', or 'cross_team'.")
    default_severity: RuleSeverity
    supported_severities: list[RuleSeverity] = Field(
        default_factory=lambda: [RuleSeverity.HARD, RuleSeverity.SOFT],
        description="Allowed severities: 'hard', 'soft'.",
    )
    supported_scopes: list[RuleScope] = Field(default_factory=list)
    required_parameters: list[str] = Field(default_factory=list)
    optional_parameters: list[str] = Field(default_factory=list)
    supported_operators: list[str] = Field(default_factory=list)
    supported_member_selections: list[str] = Field(default_factory=list)
    supported_aggregations: list[str] = Field(default_factory=list)
    accepted_value_types: list[str] = Field(default_factory=list)
    missing_data_behavior: str = Field(default="")
    parameters_schema: dict[str, Any] = Field(default_factory=dict)
