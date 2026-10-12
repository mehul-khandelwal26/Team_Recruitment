"""Schemas for signal extraction contracts, evidence, and extractor descriptors.

Defines the interface for selective signal extraction without executing
extractors prematurely.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Signal Extraction Statuses
# ---------------------------------------------------------------------------


class SignalStatus(str, Enum):
    """Lifecycle status of a signal evaluation."""

    PENDING = "pending"                  # Extractor enabled, but extraction not yet performed
    EXTRACTED = "extracted"              # Signal successfully extracted with valid value
    FAILED = "failed"                    # Extraction attempted but failed (e.g. rate limit, bad URL)
    SKIPPED = "skipped"                  # Extractor not selected by organizer
    NOT_APPLICABLE = "not_applicable"    # Input data missing (e.g. member did not provide GitHub URL)


# ---------------------------------------------------------------------------
# Signal Provenance and Evidence
# ---------------------------------------------------------------------------


class SignalEvidence(BaseModel):
    """Provenance and audit trail for an extracted signal."""

    source: str = Field(..., description="Source system or document (e.g. 'github_api', 'resume_pdf')")
    raw_input: Optional[str] = Field(None, description="Input URL, text, or file reference utilized")
    extracted_at: Optional[str] = Field(None, description="ISO-8601 timestamp of extraction")
    confidence: Optional[float] = Field(None, description="Extractor confidence level (0.0 to 1.0)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Detailed diagnostic or audit info")


# ---------------------------------------------------------------------------
# Extracted Signal Model
# ---------------------------------------------------------------------------


class ExtractedSignal(BaseModel):
    """A single evaluation signal derived for a candidate or team."""

    signal_key: str = Field(..., description="Unique signal identifier (e.g. 'github_repo_count')")
    category: str = Field(..., description="Domain category: 'technical', 'academic', 'experience', etc.")
    value: Any = Field(None, description="Extracted metric value or structured data")
    status: SignalStatus = Field(SignalStatus.PENDING, description="Current extraction status")
    error_message: Optional[str] = Field(None, description="Error detail if status is FAILED")
    evidence: Optional[SignalEvidence] = Field(None, description="Audit trail and provenance")


# ---------------------------------------------------------------------------
# Extractor Descriptor (Contract)
# ---------------------------------------------------------------------------


class ExtractorDescriptor(BaseModel):
    """Metadata describing a pluggable signal extractor."""

    extractor_id: str = Field(..., description="Unique extractor identifier (e.g. 'github_analyzer')")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Detailed description of what this extractor analyzes")
    category: str = Field(..., description="Signal category: 'technical', 'academic', 'resume', etc.")
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
    is_enabled_by_default: bool = Field(
        False,
        description="Whether this extractor runs automatically when not explicitly configured",
    )
