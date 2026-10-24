"""Schemas defining the architectural boundaries, criteria, and results for weighted scoring.

Establishes strict contracts for:
1. Criterion types, normalization, and member-to-team aggregations.
2. Missing-data policies (EXCLUDE_AND_RENORMALIZE, ZERO_SCORE).
3. Immutable, versioned scoring configurations.
4. Detailed, transparent criterion breakdowns and team score summaries.
5. Preserving eligibility outcomes without mutating them.
"""

from __future__ import annotations

import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

from app.rules.schemas import EligibilityStatus


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CriterionType(str, Enum):
    """How a criterion evaluates and normalizes a signal."""

    NUMERIC_RANGE = "numeric_range"       # Linear min-max scaling to [0.0, 1.0]
    BOOLEAN = "boolean"                   # Discrete mapping for True/False to [0.0, 1.0]
    CATEGORICAL = "categorical"           # Explicit category-to-score lookup table
    # Backward compatibility aliases
    NUMERIC_WEIGHT = "numeric_range"
    BOOLEAN_BONUS = "boolean"
    CATEGORY_MATCH = "categorical"


class AggregationMethod(str, Enum):
    """Method used to aggregate member-level scores into a team criterion score."""

    MEAN = "mean"               # Average of valid member scores
    MIN = "min"                 # Minimum valid member score
    MAX = "max"                 # Maximum valid member score
    SUM = "sum"                 # Clamped sum of valid member scores (capped at 1.0)
    LEAD_ONLY = "lead_only"     # Designated team lead's score
    TOP_K = "top_k"             # Average of the highest K valid member scores


class MissingDataPolicy(str, Enum):
    """Policy applied when a signal is missing, failed, or unextracted."""

    EXCLUDE_AND_RENORMALIZE = "exclude_and_renormalize"  # Exclude from denominator and renormalize weights
    ZERO_SCORE = "zero_score"                            # Assign 0.0 and retain full weight


class ScoreStatus(str, Enum):
    """Evaluation status for a team's composite score."""

    CALCULATED = "CALCULATED"         # Successfully scored with one or more applicable criteria
    NO_SCORE = "NO_SCORE"             # No applicable criteria could be evaluated (e.g. all missing)
    DISQUALIFIED = "DISQUALIFIED"     # Disqualified by eligibility policy (score suppressed or zero)
    NEEDS_REVIEW = "NEEDS_REVIEW"     # Missing critical data requiring organizer attention


# ---------------------------------------------------------------------------
# Normalization Configuration Models
# ---------------------------------------------------------------------------


class LinearRangeConfig(BaseModel):
    """Parameters for min-max linear range normalization."""

    min_value: float = Field(..., description="Value mapped to normalized 0.0")
    max_value: float = Field(..., description="Value mapped to normalized 1.0")

    @model_validator(mode="after")
    def validate_bounds(self) -> LinearRangeConfig:
        if self.max_value <= self.min_value:
            raise ValueError(f"max_value ({self.max_value}) must be strictly greater than min_value ({self.min_value})")
        return self


class BooleanMappingConfig(BaseModel):
    """Parameters for mapping boolean states to scores in [0.0, 1.0]."""

    true_score: float = Field(1.0, ge=0.0, le=1.0, description="Normalized score when signal is True")
    false_score: float = Field(0.0, ge=0.0, le=1.0, description="Normalized score when signal is False")


class CategoricalMappingConfig(BaseModel):
    """Parameters for mapping discrete categories to scores in [0.0, 1.0]."""

    category_scores: dict[str, float] = Field(
        ...,
        description="Lookup table from categorical value string to normalized score in [0.0, 1.0]",
    )
    default_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Optional fallback score for unlisted categories. If None, unlisted category is treated as missing.",
    )
    case_sensitive: bool = Field(False, description="Whether category matching is case-sensitive")

    @field_validator("category_scores")
    @classmethod
    def validate_scores(cls, v: dict[str, float]) -> dict[str, float]:
        if not v:
            raise ValueError("category_scores dictionary cannot be empty")
        for cat, score in v.items():
            if not isinstance(score, (int, float)) or score < 0.0 or score > 1.0:
                raise ValueError(f"Category '{cat}' score must be a finite number between 0.0 and 1.0; got {score}")
        return v


class NormalizationConfig(BaseModel):
    """Polymorphic container for normalization settings."""

    linear_range: Optional[LinearRangeConfig] = None
    boolean_mapping: Optional[BooleanMappingConfig] = None
    categorical_mapping: Optional[CategoricalMappingConfig] = None


class ConfidenceConfig(BaseModel):
    """Optional configuration for adjusting scores by extractor confidence."""

    enabled: bool = Field(False, description="Whether to scale criterion score by extractor confidence")
    min_confidence: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold. Below this, signal is treated as unextracted.",
    )


# ---------------------------------------------------------------------------
# Evaluation Criterion Definition
# ---------------------------------------------------------------------------


class EvaluationCriterion(BaseModel):
    """An individual scoring criterion configured by the organizer."""

    criterion_id: str = Field(..., min_length=1, description="Unique criterion identifier")
    name: str = Field(..., min_length=1, description="Human-readable name")
    description: Optional[str] = Field(None, description="Detailed explanation of what this criterion evaluates")
    target_signal_key: str = Field(..., min_length=1, description="Signal key to evaluate (e.g. 'github_public_repo_count')")
    criterion_type: CriterionType = Field(..., description="Criterion type (numeric_range, boolean, categorical)")
    weight: float = Field(1.0, ge=0.0, description="Relative non-negative weight")
    is_enabled: bool = Field(True, description="Whether this criterion contributes to the final score")

    # Normalization & Aggregation
    normalization: NormalizationConfig = Field(
        default_factory=NormalizationConfig,
        description="Normalization configuration matching the criterion_type",
    )
    aggregation: AggregationMethod = Field(
        AggregationMethod.MEAN,
        description="Member-to-team score aggregation method",
    )
    top_k_value: Optional[int] = Field(
        None,
        ge=1,
        description="Value of K when aggregation is 'top_k'",
    )

    # Missing Data & Confidence
    missing_data_policy: MissingDataPolicy = Field(
        MissingDataPolicy.EXCLUDE_AND_RENORMALIZE,
        description="How missing/unextracted signals for this criterion are handled",
    )
    confidence_adjustment: ConfidenceConfig = Field(
        default_factory=ConfidenceConfig,
        description="Optional confidence scaling settings",
    )

    # Backward compatibility: legacy config dict
    config: dict[str, Any] = Field(default_factory=dict, description="Arbitrary extra parameters")

    @model_validator(mode="before")
    @classmethod
    def handle_legacy_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "is_selected" in data and "is_enabled" not in data:
                data["is_enabled"] = data["is_selected"]
        return data

    @property
    def is_selected(self) -> bool:
        return self.is_enabled

    @is_selected.setter
    def is_selected(self, val: bool) -> None:
        self.is_enabled = val


# ---------------------------------------------------------------------------
# Scoring Configuration
# ---------------------------------------------------------------------------


class ScoringConfiguration(BaseModel):
    """Organizer-controlled configuration bundle for an evaluation run."""

    config_id: str = Field(..., min_length=1, description="Unique configuration identifier")
    user_id: Optional[str] = Field(None, description="Owning user identifier for multi-tenant isolation")
    name: str = Field(..., min_length=1, description="Human-readable configuration name")
    version: int = Field(1, ge=1, description="Immutable version number, auto-incremented on update")
    description: Optional[str] = Field(None, description="Description of scoring rubric and intent")
    criteria: list[EvaluationCriterion] = Field(
        default_factory=list,
        description="List of configured scoring criteria",
    )
    scale_max: float = Field(100.0, gt=0.0, description="Maximum scale for the composite score (default 100.0)")

    # Team Lead Resolution Settings
    lead_field: Optional[str] = Field("role", description="Registration field key identifying member role")
    lead_values: list[str] = Field(
        default_factory=lambda: ["lead", "team lead", "captain", "leader"],
        description="Values in lead_field identifying the designated team lead",
    )

    # Eligibility Policy
    score_ineligible_teams: bool = Field(
        True,
        description="If True, calculate informational scores for INELIGIBLE teams. If False, assign 0.0 / DISQUALIFIED.",
    )
    is_active: bool = Field(True, description="Whether this configuration is active")
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def handle_legacy_config_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "selected_criteria" in data and "criteria" not in data:
                data["criteria"] = data["selected_criteria"]
        return data

    @property
    def selected_criteria(self) -> list[EvaluationCriterion]:
        return self.criteria

    @selected_criteria.setter
    def selected_criteria(self, val: list[EvaluationCriterion]) -> None:
        self.criteria = val


class ScoringConfigurationCreate(BaseModel):
    """Payload for creating a new scoring configuration (starts at version 1)."""

    config_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    criteria: list[EvaluationCriterion] = Field(default_factory=list)
    scale_max: float = Field(100.0, gt=0.0)
    lead_field: Optional[str] = "role"
    lead_values: list[str] = Field(default_factory=lambda: ["lead", "team lead", "captain", "leader"])
    score_ineligible_teams: bool = True


class ScoringConfigurationUpdate(BaseModel):
    """Payload for updating a configuration (creates a new immutable version)."""

    name: Optional[str] = None
    description: Optional[str] = None
    criteria: Optional[list[EvaluationCriterion]] = None
    scale_max: Optional[float] = Field(None, gt=0.0)
    lead_field: Optional[str] = None
    lead_values: Optional[list[str]] = None
    score_ineligible_teams: Optional[bool] = None
    is_active: Optional[bool] = None


# ---------------------------------------------------------------------------
# Score Breakdown Models
# ---------------------------------------------------------------------------


class MemberScoreDetail(BaseModel):
    """Scoring detail for an individual member under a specific criterion."""

    member_id: str
    member_name: str
    raw_value: Any = None
    signal_status: Optional[str] = None
    provenance: Optional[str] = None
    confidence: Optional[float] = None
    normalized_score: Optional[float] = None
    is_contributing: bool = True
    exclusion_reason: Optional[str] = None


class CriterionScoreBreakdown(BaseModel):
    """Comprehensive, explainable breakdown for a single criterion."""

    criterion_id: str
    name: str
    target_signal_key: str
    criterion_type: CriterionType
    configured_weight: float
    normalized_weight: float
    raw_values: dict[str, Any] = Field(default_factory=dict, description="member_id -> raw_value")
    signal_statuses: dict[str, str] = Field(default_factory=dict, description="member_id -> SignalStatus")
    normalization_method: str
    aggregation_method: str
    team_criterion_score: Optional[float] = Field(
        None,
        description="Aggregated team score in [0.0, 1.0], or None if uncalculated",
    )
    weighted_contribution: float = Field(
        0.0,
        description="Contribution points added to final team score (out of scale_max)",
    )
    missing_data_policy: MissingDataPolicy
    is_applicable: bool = True
    missing_data_applied: bool = False
    member_scores: list[MemberScoreDetail] = Field(default_factory=list)
    explanation: str


class TeamScoringResult(BaseModel):
    """Complete scoring result and diagnostic audit for a single team."""

    team_id: str
    team_name: str
    final_score: Optional[float] = Field(None, description="Calculated composite score in [0.0, scale_max]")
    score_status: ScoreStatus
    total_configured_weight: float
    applicable_weight: float
    weight_renormalized: bool = False
    criteria_breakdowns: list[CriterionScoreBreakdown] = Field(default_factory=list)
    eligibility_status: Optional[EligibilityStatus] = None
    eligibility_summary: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)
    explanation: str
    is_temporary_id: bool = Field(default=False, description="Whether this team was assigned a temporary ID due to missing/ambiguous ID")
    is_unresolved: bool = Field(default=False, description="Whether this team's identity is unresolved due to duplicate names or ambiguous registration")


class ScoringRunSummary(BaseModel):
    """Aggregate statistics for an evaluation run."""

    total_teams: int = 0
    calculated_teams: int = 0
    no_score_teams: int = 0
    disqualified_teams: int = 0
    needs_review_teams: int = 0
    average_score: Optional[float] = None
    min_score: Optional[float] = None
    max_score: Optional[float] = None


class ScoringRunResponse(BaseModel):
    """Standard response model for a completed scoring evaluation run."""

    run_id: str
    config_id: str
    config_version: int
    evaluated_at: str
    teams: list[TeamScoringResult]
    summary: ScoringRunSummary
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    eligibility_run_id: Optional[str] = Field(
        default=None,
        description="Source eligibility run ID if linked.",
    )
    dataset_id: Optional[str] = Field(
        default=None,
        description="Source dataset ID if evaluated from a stored dataset.",
    )
    user_id: Optional[str] = Field(
        default=None,
        description="Owner user ID for isolated workspaces.",
    )
    extraction_run_id: Optional[str] = Field(
        default=None,
        description="Source extraction run ID if linked.",
    )
    config_source: Optional[str] = Field(
        default=None,
        description="Configuration origin: 'stored' for store presets/configs or 'inline' for ad-hoc configs.",
    )
    config_snapshot: Optional[ScoringConfiguration] = Field(
        default=None,
        description="Full snapshot of the exact scoring configuration used (set only for inline runs).",
    )


class ScoringEvaluationRequest(BaseModel):
    """Request payload for evaluating teams against a scoring configuration."""

    teams: Optional[list[dict[str, Any]]] = Field(
        None,
        description="List of TeamSchema objects or team dictionaries. Optional if dataset_id is provided.",
    )
    signals: Optional[list[dict[str, Any]]] = Field(
        None,
        description="Pre-extracted signals per member (MemberSignals payload). The engine never calls analyzers.",
    )
    config_id: Optional[str] = Field(None, description="Config ID to use from store (default: uses latest)")
    config_version: Optional[int] = Field(None, description="Optional explicit version of config_id")
    inline_config: Optional[ScoringConfiguration] = Field(None, description="Optional ad-hoc configuration")
    eligibility_run_id: Optional[str] = Field(
        None,
        description="Optional run_id of an eligibility run to associate outcomes from store",
    )
    eligibility_results: Optional[list[dict[str, Any]]] = Field(
        None,
        description="Optional explicit team eligibility results to associate directly",
    )
    dataset_id: Optional[str] = Field(
        None,
        description="Optional dataset identifier if evaluated from a stored dataset.",
    )
    extraction_run_id: Optional[str] = Field(
        None,
        description="Optional extraction run identifier if linked.",
    )

    @model_validator(mode="after")
    def validate_teams_or_dataset(self) -> ScoringEvaluationRequest:
        if self.teams is None and self.dataset_id is None and self.eligibility_run_id is None:
            raise ValueError("Must provide either 'teams', 'dataset_id', or 'eligibility_run_id'.")
        return self



class ScoringCatalogResponse(BaseModel):
    """Catalog describing all supported scoring capabilities."""

    criterion_types: list[dict[str, Any]]
    normalization_methods: list[dict[str, Any]]
    aggregation_methods: list[dict[str, Any]]
    missing_data_policies: list[dict[str, Any]]


class ScoringRunAudit(BaseModel):
    """Audit record capturing the exact boundary between data, signals, and scoring."""

    run_id: str
    registration_fields_detected: list[str] = Field(
        default_factory=list,
        description="All fields present in registration data (does not imply evaluated)",
    )
    extracted_signals_available: list[str] = Field(
        default_factory=list,
        description="Signals successfully derived by enabled extractors",
    )
    organizer_selected_criteria: list[str] = Field(
        default_factory=list,
        description="Criteria explicitly activated by organizer",
    )
    criteria_actually_evaluated: list[str] = Field(
        default_factory=list,
        description="Intersection of available signals and selected criteria used in run",
    )
