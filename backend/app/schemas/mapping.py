"""Schemas and configuration for field mapping and discovery.

Defines canonical application fields, aliases for suggestions,
and models for discovery and explicit mapping configurations.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Canonical Target Fields
# ---------------------------------------------------------------------------


class CanonicalField(str, Enum):
    """Recognized application concepts to which registration columns can map."""

    # Core structural fields
    TEAM_ID = "team_id"
    TEAM_NAME = "team_name"
    MEMBER_ID = "member_id"
    MEMBER_NAME = "name"

    # Standard profile & contact fields
    EMAIL = "email"
    RESUME_URL = "resume_url"
    GITHUB_URL = "github_url"
    LINKEDIN_URL = "linkedin_url"
    PORTFOLIO_URL = "portfolio_url"

    # Academic & candidate metrics
    CGPA = "cgpa"
    ACADEMIC_YEAR = "academic_year"


# Known aliases for fuzzy / suggestion matching
CANONICAL_ALIASES: dict[str, list[str]] = {
    CanonicalField.TEAM_ID.value: [
        "team_id", "team id", "teamid", "team_identifier", "team identifier",
        "group_id", "group id", "groupid",
    ],
    CanonicalField.TEAM_NAME.value: [
        "team_name", "team name", "teamname", "team", "group_name", "group name",
        "group", "project team", "team title",
    ],
    CanonicalField.MEMBER_ID.value: [
        "member_id", "member id", "memberid", "participant_id", "participant id",
        "participantid", "student_id", "student id", "roll_no", "roll no",
        "roll number", "registration_number", "reg_no", "reg no",
        "member_number", "member number", "member_no", "member no",
    ],
    CanonicalField.MEMBER_NAME.value: [
        "name", "member_name", "member name", "full_name", "full name",
        "participant_name", "participant name", "candidate_name", "candidate name",
        "student_name", "student name", "student",
    ],
    CanonicalField.EMAIL.value: [
        "email", "email_address", "email address", "e-mail", "mail",
        "contact_email", "email id", "email_id",
    ],
    CanonicalField.RESUME_URL.value: [
        "resume_url", "resume url", "resume", "cv", "cv_url", "cv url",
        "resume_link", "resume link", "curriculum vitae",
        "resume_path", "resume path", "resume_file", "resume file",
    ],
    CanonicalField.GITHUB_URL.value: [
        "github_url", "github url", "github", "github_profile", "github profile",
        "github link", "github_handle", "github handle", "github_id", "github id",
    ],
    CanonicalField.LINKEDIN_URL.value: [
        "linkedin_url", "linkedin url", "linkedin", "linkedin_profile",
        "linkedin profile", "linkedin link",
    ],
    CanonicalField.PORTFOLIO_URL.value: [
        "portfolio_url", "portfolio url", "portfolio", "portfolio_link",
        "portfolio link", "website", "personal_website", "portfolio website",
    ],
    CanonicalField.CGPA.value: [
        "cgpa", "gpa", "cpi", "grade point average", "academic score", "grades",
    ],
    CanonicalField.ACADEMIC_YEAR.value: [
        "academic_year", "academic year", "year", "year_of_study", "year of study",
        "batch", "grad_year", "graduation_year", "class",
    ],
}

# Structural fields required to build valid team & member hierarchies
REQUIRED_STRUCTURAL_FIELDS: set[str] = {
    CanonicalField.TEAM_ID.value,
    CanonicalField.TEAM_NAME.value,
    CanonicalField.MEMBER_ID.value,
    CanonicalField.MEMBER_NAME.value,
}


# ---------------------------------------------------------------------------
# Models for Field Discovery & Metadata
# ---------------------------------------------------------------------------


class CanonicalFieldInfo(BaseModel):
    """Information about a recognized application concept."""

    field_key: str
    display_name: str
    is_structural_required: bool
    description: str
    category: str


class DiscoveredField(BaseModel):
    """Metadata describing a column or property discovered in registration data."""

    original_name: str = Field(..., description="Exact field name in the uploaded file")
    normalized_key: str = Field(..., description="Lowercased and stripped key used for matching")
    inferred_type: str = Field(..., description="Inferred data type: string, number, email, url, etc.")
    sample_values: list[Any] = Field(default_factory=list, description="Up to 3 non-empty sample values")
    total_count: int = Field(0, description="Total rows or records inspected")
    non_empty_count: int = Field(0, description="Count of rows with non-empty values")
    missing_count: int = Field(0, description="Count of rows where value is null or empty")
    is_consistently_populated: bool = Field(True, description="True if non-empty in >=80% of rows")
    is_recognized: bool = Field(False, description="True if matches a canonical field directly")
    recognized_field: Optional[str] = Field(None, description="Directly recognized canonical field key")
    suggested_mapping: Optional[str] = Field(None, description="Suggested canonical field mapping")
    suggestion_confidence: float = Field(0.0, description="Confidence score between 0.0 and 1.0")
    suggestion_reason: Optional[str] = Field(None, description="Explanation for the suggestion")
    is_structural_required: bool = Field(False, description="True if this is a required structural field")
    status: str = Field("unmapped", description="'recognized', 'suggested', or 'unmapped'")


class FieldDiscoveryResponse(BaseModel):
    """Response returned by the registration inspection / discovery endpoint."""

    file_name: str
    file_type: str
    total_records: int
    total_teams_detected: Optional[int] = None
    total_members_detected: Optional[int] = None
    discovered_fields: list[DiscoveredField] = Field(default_factory=list)
    missing_structural_fields: list[str] = Field(
        default_factory=list,
        description="Required structural fields not yet matched or suggested",
    )
    suggested_mappings: dict[str, str] = Field(
        default_factory=dict,
        description="Suggested mapping dictionary: original_name -> canonical_field",
    )
    canonical_fields: list[CanonicalFieldInfo] = Field(
        default_factory=list,
        description="List of all available canonical target fields for organizer reference",
    )


class FieldMappingConfig(BaseModel):
    """Explicit mapping from organizer's original column names to canonical fields."""

    mappings: dict[str, str] = Field(
        ...,
        description="Map of original column name -> canonical field name (e.g. {'Participant Name': 'name'})",
    )
