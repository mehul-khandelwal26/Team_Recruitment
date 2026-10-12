"""Schemas defining the architectural boundaries for organizer-controlled scoring.

Establishes the separation between:
1. Registration fields present
2. Extracted signals
3. Available evaluation criteria
4. Explicitly selected criteria
5. Active scoring run execution
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class CriterionType(str, Enum):
    """How a criterion evaluates a signal or registration field."""

    NUMERIC_WEIGHT = "numeric_weight"       # Score proportional to numeric signal value
    THRESHOLD_PASS = "threshold_pass"       # Minimum requirement or cutoff
    BOOLEAN_BONUS = "boolean_bonus"         # Bonus points for affirmative signal
    CATEGORY_MATCH = "category_match"       # Specific values map to specific scores
    MANUAL_REVIEW = "manual_review"         # Organizer review score


class EvaluationCriterion(BaseModel):
    """An evaluation rule or weight explicitly chosen by the organizer."""

    criterion_id: str = Field(..., description="Unique criterion identifier")
    name: str = Field(..., description="Display name for organizer dashboard")
    criterion_type: CriterionType = Field(..., description="Evaluation logic type")
    target_signal_key: str = Field(
        ...,
        description="The signal or normalized field this criterion evaluates (never applied automatically)",
    )
    weight: float = Field(1.0, ge=0.0, description="Relative weight in final composite score")
    is_selected: bool = Field(
        False,
        description="Must be explicitly True for this criterion to be used in scoring",
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Thresholds, ranges, or bonus point mappings",
    )
    description: Optional[str] = Field(None, description="Organizer explanation of purpose")


class ScoringConfiguration(BaseModel):
    """Organizer-controlled configuration bundle for an evaluation run."""

    config_id: str
    name: str
    selected_criteria: list[EvaluationCriterion] = Field(
        default_factory=list,
        description="Only criteria in this list will be utilized during scoring",
    )
    scale_max: float = Field(100.0, description="Target maximum composite score")
    missing_data_strategy: str = Field(
        "penalize_zero",
        description="How unextracted signals are treated (e.g. 'neutral_mean', 'zero', 'exclude_weight')",
    )


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
