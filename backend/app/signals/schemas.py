"""Schemas for signal extraction contracts, evidence, descriptors, and execution results.

Defines the interface for selective signal extraction, categorization,
provenance tracking, and multi-team/multi-member result models.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any, Optional
from pydantic import BaseModel, Field, model_validator

if TYPE_CHECKING:
    from app.schemas.ingestion import TeamSchema


# ---------------------------------------------------------------------------
# Signal Extraction Statuses
# ---------------------------------------------------------------------------


class SignalStatus(str, Enum):
    """Lifecycle status of a signal evaluation."""

    PENDING = "pending"                  # Extractor enabled, but extraction not yet performed
    EXTRACTED = "extracted"              # Signal successfully extracted with valid value
    FAILED = "failed"                    # Extraction attempted but failed (e.g. rate limit, bad URL, validation error)
    SKIPPED = "skipped"                  # Extractor not selected by organizer
    NOT_APPLICABLE = "not_applicable"    # Input data missing (e.g. member did not provide GitHub URL or CGPA)


# ---------------------------------------------------------------------------
# Signal Provenance and Evidence
# ---------------------------------------------------------------------------


class SignalEvidence(BaseModel):
    """Provenance and audit trail for an extracted signal."""

    source: str = Field(..., description="Source system or document (e.g. 'github_api', 'registration_data')")
    raw_input: Optional[str] = Field(None, description="Input URL, text, or file reference utilized")
    extracted_at: Optional[str] = Field(None, description="ISO-8601 timestamp of extraction")
    confidence: Optional[float] = Field(None, description="Extractor confidence level (0.0 to 1.0)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Detailed diagnostic or audit info")


# ---------------------------------------------------------------------------
# Extracted Signal Model
# ---------------------------------------------------------------------------


class ExtractedSignal(BaseModel):
    """A single evaluation signal derived for a candidate or team."""

    signal_key: str = Field(..., description="Unique signal identifier (e.g. 'github_public_repo_count')")
    category: str = Field(..., description="Domain category: 'github', 'academic', 'technical', etc.")
    value: Any = Field(None, description="Extracted metric value or structured data")
    status: SignalStatus = Field(SignalStatus.PENDING, description="Current extraction status")
    error_message: Optional[str] = Field(None, description="Error detail if status is FAILED or NOT_APPLICABLE")
    warning_message: Optional[str] = Field(None, description="Non-fatal warning if applicable")
    evidence: Optional[SignalEvidence] = Field(None, description="Audit trail and provenance")


# ---------------------------------------------------------------------------
# Signal & Category Metadata Definitions
# ---------------------------------------------------------------------------


class SignalDefinition(BaseModel):
    """Metadata describing an individual signal supported by an analyzer."""

    signal_key: str = Field(..., description="Unique signal identifier")
    name: str = Field(..., description="Human-readable signal display name")
    description: str = Field(..., description="Detailed description of what this signal measures")
    category: str = Field(..., description="Broad category identifier this signal belongs to")
    value_type: str = Field(..., description="Data type: 'integer', 'float', 'string', 'boolean', 'dict', 'list'")
    unit: Optional[str] = Field(None, description="Optional unit of measurement (e.g. 'repos', 'points')")


class CategoryDefinition(BaseModel):
    """Broad category grouping related signals and analyzers."""

    category_id: str = Field(..., description="Unique category identifier (e.g. 'github', 'academic')")
    name: str = Field(..., description="Display name of the category")
    description: str = Field(..., description="Description of the category")
    signal_keys: list[str] = Field(default_factory=list, description="Keys of signals in this category")


# ---------------------------------------------------------------------------
# Extractor Descriptor (Contract)
# ---------------------------------------------------------------------------


class ExtractorDescriptor(BaseModel):
    """Metadata describing a pluggable signal extractor."""

    extractor_id: str = Field(..., description="Unique extractor identifier (e.g. 'github_analyzer')")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Detailed description of what this extractor analyzes")
    category: str = Field(..., description="Signal category: 'github', 'academic', 'technical', etc.")
    required_inputs: list[str] = Field(
        ...,
        description="List of canonical or custom field keys needed to run (e.g. ['github_url'])",
    )
    optional_inputs: list[str] = Field(
        default_factory=list,
        description="Optional fields that enhance extraction if available",
    )
    produced_signals: list[str] = Field(
        ...,
        description="List of signal keys this extractor produces",
    )
    signals: list[SignalDefinition] = Field(
        default_factory=list,
        description="Detailed definitions for each produced signal",
    )
    is_enabled_by_default: bool = Field(
        False,
        description="Whether this extractor runs automatically when not explicitly configured",
    )
    optional_config: dict[str, Any] = Field(
        default_factory=dict,
        description="Configuration options accepted by the extractor",
    )


# ---------------------------------------------------------------------------
# Multi-Team & Multi-Member Result Schemas
# ---------------------------------------------------------------------------


class MemberExtractionResult(BaseModel):
    """Extraction results for a single team member."""

    member_id: str = Field(..., description="Member identifier")
    name: str = Field(..., description="Member display name")
    signals: list[ExtractedSignal] = Field(default_factory=list, description="Signals extracted for this member")


class TeamExtractionResult(BaseModel):
    """Extraction results for a team with member-level signal associations preserved."""

    team_id: str = Field(..., description="Team identifier")
    team_name: str = Field(..., description="Team display name")
    is_temporary_id: bool = Field(
        default=False,
        description="Whether this team has a temporary unresolved ID",
    )
    is_unresolved: bool = Field(
        default=False,
        description="Whether this team's identity is unresolved due to duplicate names or ambiguous registration",
    )
    member_results: list[MemberExtractionResult] = Field(
        default_factory=list,
        description="Per-member extraction results",
    )


class ExtractionRunRequest(BaseModel):
    """Request model for running signal extraction against teams."""

    teams: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description="List of teams (e.g. from /api/ingestion/upload) with member hierarchies. If omitted, loaded from dataset_id.",
    )
    dataset_id: Optional[str] = Field(
        default=None,
        description="Optional dataset identifier to load teams from stored dataset or associate run with dataset.",
    )
    selected_signals: Optional[list[str]] = Field(
        None,
        description="List of individual signal keys to extract. If omitted or null, all supported signals run.",
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional organizer-provided configuration (e.g. scale settings, column overrides)",
    )

    @model_validator(mode="after")
    def validate_teams_or_dataset(self) -> ExtractionRunRequest:
        if self.teams is None and self.dataset_id is None:
            raise ValueError("Must provide either teams or dataset_id.")
        return self


class ExtractionRunResponse(BaseModel):
    """Standardized response returned by signal extraction runs."""

    run_id: str = Field(..., description="Unique extraction run identifier")
    teams: list[TeamExtractionResult] = Field(default_factory=list, description="Extracted signals per team and member")
    selected_signals: list[str] = Field(default_factory=list, description="Signals selected for this run")
    analyzers_executed: list[str] = Field(default_factory=list, description="Analyzers that executed in this run")
    total_teams: int = 0
    total_members: int = 0
    warnings: list[str] = Field(default_factory=list, description="Run-level warnings")
    errors: list[str] = Field(default_factory=list, description="Run-level non-fatal errors")
    dataset_id: Optional[str] = Field(
        default=None,
        description="Optional dataset identifier if extraction was executed against a stored dataset snapshot.",
    )
    created_at: Optional[str] = Field(
        default=None,
        description="ISO 8601 execution and creation timestamp.",
    )


class SignalCatalogResponse(BaseModel):
    """Catalog of all registered categories, analyzers, and supported signals."""

    categories: list[CategoryDefinition] = Field(default_factory=list)
    analyzers: list[ExtractorDescriptor] = Field(default_factory=list)
    signals: list[SignalDefinition] = Field(default_factory=list)
