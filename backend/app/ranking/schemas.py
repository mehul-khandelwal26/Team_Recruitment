"""Schemas defining ranking models, top-X selection, and explainable audit trails.

Contracts:
- Deterministic ordinal ranks based on descending final score, optional tiebreak criteria, and team_id.
- Explicit status handling (ELIGIBLE, INELIGIBLE, NEEDS_REVIEW, NO_SCORE, DISQUALIFIED, UNRESOLVED).
- Explainable selection results preserving upstream scoring breakdowns and completeness metrics.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator

from app.rules.schemas import EligibilityStatus
from app.scoring.schemas import (
    CriterionScoreBreakdown,
    ScoreStatus,
    ScoringConfiguration,
    TeamScoringResult,
)


class SelectionStatus(str, Enum):
    """Selection outcome for a team under a Top-X ranking run."""

    SELECTED = "SELECTED"          # Shortlisted in Top-X
    NOT_SELECTED = "NOT_SELECTED"  # Qualified and ranked, but fell below the cutoff
    NEEDS_REVIEW = "NEEDS_REVIEW"  # Excluded from main shortlist pending organizer manual review
    EXCLUDED = "EXCLUDED"          # Excluded (ineligible, disqualified, no score, or unresolved)


class ExclusionReason(str, Enum):
    """Reason code explaining why a team was excluded from automatic selection."""

    INELIGIBLE = "INELIGIBLE"      # Failed hard eligibility criteria
    NEEDS_REVIEW = "NEEDS_REVIEW"  # Flagged for manual review (include_needs_review is False)
    NO_SCORE = "NO_SCORE"          # No calculable composite score (missing/unextracted data)
    DISQUALIFIED = "DISQUALIFIED"  # Disqualified during scoring or eligibility evaluation
    UNRESOLVED = "UNRESOLVED"      # Ambiguous duplicate team name or temporary registration ID


class RankedTeamResult(BaseModel):
    """Individual team ranking result and explainable breakdown."""

    team_id: str = Field(..., description="Unique team identifier.")
    team_name: str = Field(..., description="Team display name.")
    rank: int = Field(..., ge=1, description="1-based ordinal rank (1, 2, 3...).")
    final_score: float = Field(..., description="Composite numerical score (includes valid 0.0).")
    score_status: ScoreStatus = Field(..., description="Score evaluation status from scoring engine.")
    eligibility_status: Optional[EligibilityStatus] = Field(
        default=None,
        description="Eligibility decision from eligibility engine, or None if unverified.",
    )
    eligibility_summary: Optional[str] = Field(
        default=None,
        description="Reasoning or failure explanation from eligibility engine.",
    )
    is_tied: bool = Field(
        default=False,
        description="True if another ranked candidate shares the exact same final score.",
    )
    tiebreak_score: Optional[float] = Field(
        default=None,
        description="Score value of configured tiebreak criterion if evaluated.",
    )
    selection_status: SelectionStatus = Field(
        ...,
        description="Whether team was selected, qualified but unselected, or flagged for review.",
    )
    criteria_breakdowns: list[CriterionScoreBreakdown] = Field(
        default_factory=list,
        description="Criterion-level audit breakdowns preserved from scoring engine.",
    )
    weight_renormalized: bool = Field(
        default=False,
        description="Whether criterion weights were renormalized due to missing data.",
    )
    applicable_weight: float = Field(
        default=0.0,
        description="Sum of weights for applicable criteria.",
    )
    total_configured_weight: float = Field(
        default=0.0,
        description="Total configured criteria weight before missing data handling.",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Diagnostic warnings pertaining to this team's score or rank.",
    )
    explanation: str = Field(
        default="",
        description="Human-readable explanation of rank, score, and selection outcome.",
    )


class ExcludedTeamResult(BaseModel):
    """Diagnostic details for a team excluded from automatic Top-X selection."""

    team_id: str = Field(..., description="Unique team identifier.")
    team_name: str = Field(..., description="Team display name.")
    reason_code: ExclusionReason = Field(..., description="Standard exclusion category code.")
    explanation: str = Field(..., description="Human-readable reason for exclusion.")
    eligibility_status: Optional[EligibilityStatus] = Field(
        default=None,
        description="Original eligibility status, preserved unchanged.",
    )
    eligibility_reasons: list[str] = Field(
        default_factory=list,
        description="Original eligibility failure reasons if available.",
    )
    score_status: Optional[ScoreStatus] = Field(
        default=None,
        description="Original score status if evaluated.",
    )
    final_score: Optional[float] = Field(
        default=None,
        description="Original score if calculated (e.g. for disqualified/needs_review teams).",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Diagnostic warnings associated with this team.",
    )


class RankingRunSummary(BaseModel):
    """Aggregate statistics for a Top-X ranking run."""

    total_teams_evaluated: int = 0
    qualifying_teams_count: int = 0
    selected_teams_count: int = 0
    shortage: int = 0
    requested_top_x: int = 0
    tie_at_cutoff: bool = False
    cutoff_score: Optional[float] = None
    excluded_count: int = 0
    needs_review_count: int = 0
    unresolved_count: int = 0
    ineligible_count: int = 0
    no_score_count: int = 0
    disqualified_count: int = 0


class RankingRunResponse(BaseModel):
    """Standard response model for a completed Top-X ranking and selection run."""

    run_id: str = Field(..., description="Unique ranking run identifier.")
    scoring_run_id: Optional[str] = Field(default=None, description="Source scoring run ID if linked.")
    eligibility_run_id: Optional[str] = Field(default=None, description="Source eligibility run ID if linked.")
    evaluated_at: str = Field(..., description="ISO 8601 execution timestamp.")
    top_x: int = Field(..., description="Requested number of shortlisted teams.")
    include_needs_review: bool = Field(
        default=False,
        description="Whether scored NEEDS_REVIEW teams participated in main selection.",
    )
    tiebreak_criterion_id: Optional[str] = Field(
        default=None,
        description="Configured criterion ID used to resolve primary score ties.",
    )
    selected_teams: list[RankedTeamResult] = Field(
        default_factory=list,
        description="Shortlisted teams qualified under the configured selection policy (up to top_x).",
    )
    ranked_teams: list[RankedTeamResult] = Field(
        default_factory=list,
        description="All qualifying teams ordered by rank.",
    )
    needs_review_teams: list[RankedTeamResult] = Field(
        default_factory=list,
        description="Scored teams requiring manual review (when include_needs_review is False).",
    )
    recommended_review_candidates: list[RankedTeamResult] = Field(
        default_factory=list,
        description="Highest-ranked NEEDS_REVIEW suggestions to fill any shortlist shortage.",
    )
    unresolved_teams: list[ExcludedTeamResult] = Field(
        default_factory=list,
        description="Teams with unresolved or temporary identities excluded from automatic selection.",
    )
    excluded_teams: list[ExcludedTeamResult] = Field(
        default_factory=list,
        description="All excluded teams categorized by reason code.",
    )
    summary: RankingRunSummary = Field(
        default_factory=RankingRunSummary,
        description="Aggregate summary counts and cutoff diagnostics.",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Run-level diagnostic warnings (e.g. shortages, ties at cutoff).",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Run-level non-fatal errors encountered.",
    )
    dataset_id: Optional[str] = Field(
        default=None,
        description="Source dataset ID if evaluated from a stored dataset.",
    )
    extraction_run_id: Optional[str] = Field(
        default=None,
        description="Source extraction run ID if linked.",
    )


class RankingEvaluationRequest(BaseModel):
    """Request payload to execute ranking and Top-X selection."""

    top_x: int = Field(
        ...,
        gt=0,
        description="Mandatory positive integer specifying number of top teams to shortlist.",
    )
    scoring_run_id: Optional[str] = Field(
        default=None,
        description="Run ID of a recorded scoring run to rank from default_scoring_run_store.",
    )
    scoring_results: Optional[list[Any]] = Field(
        default=None,
        description="Explicit list of TeamScoringResult dicts or objects to rank.",
    )
    teams: Optional[list[Any]] = Field(
        default=None,
        description="Raw teams list to evaluate end-to-end through scoring then ranking.",
    )
    signals: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description="Optional signals payload if evaluating end-to-end.",
    )
    scoring_config_id: Optional[str] = Field(
        default=None,
        description="Scoring configuration ID if evaluating end-to-end.",
    )
    scoring_config_version: Optional[int] = Field(
        default=None,
        description="Optional version of scoring_config_id.",
    )
    inline_scoring_config: Optional[ScoringConfiguration] = Field(
        default=None,
        description="Optional ad-hoc scoring configuration if evaluating end-to-end.",
    )
    eligibility_run_id: Optional[str] = Field(
        default=None,
        description="Optional eligibility run ID to correlate.",
    )
    eligibility_results: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description="Optional explicit eligibility result dicts to correlate.",
    )
    tiebreak_criterion_id: Optional[str] = Field(
        default=None,
        description="Optional criterion ID used to break primary final_score ties.",
    )
    include_needs_review: bool = Field(
        default=False,
        description="Whether scored NEEDS_REVIEW teams may participate in main Top-X selection.",
    )
    run_id: Optional[str] = Field(
        default=None,
        description="Optional injected run ID for deterministic testing.",
    )
    evaluated_at: Optional[str] = Field(
        default=None,
        description="Optional injected ISO timestamp for deterministic testing.",
    )

    @field_validator("top_x", mode="before")
    @classmethod
    def validate_top_x_not_bool(cls, v: Any) -> Any:
        if isinstance(v, bool):
            raise ValueError("top_x cannot be a boolean value")
        if not isinstance(v, int):
            try:
                v = int(v)
            except (ValueError, TypeError):
                raise ValueError("top_x must be a positive integer (> 0)")
        if v <= 0:
            raise ValueError(f"top_x must be a positive integer (> 0), got {v}")
        return v
