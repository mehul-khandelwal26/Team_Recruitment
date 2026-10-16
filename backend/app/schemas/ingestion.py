"""Pydantic schemas for registration data ingestion and dynamic form models.

Defines the data structures for team members, teams, custom fields,
raw registration preservation, missing-data tracking, and upload responses.
All schemas use Pydantic v2 conventions.
"""

from __future__ import annotations

import datetime
from enum import Enum
from typing import Any, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Missing-data state tracking
# ---------------------------------------------------------------------------


class FieldPresenceStatus(str, Enum):
    """Explicit lifecycle status for individual fields in a registration."""

    NOT_COLLECTED = "not_collected"      # Organizer form did not collect this field
    COLLECTED_BLANK = "collected_blank"  # Field existed on form, but was left blank/null
    PRESENT = "present"                  # Field was provided and passed validation
    INVALID = "invalid"                  # Field was provided but failed format/data validation


# ---------------------------------------------------------------------------
# Member schema
# ---------------------------------------------------------------------------


KNOWN_MEMBER_FIELDS = {
    "member_id",
    "name",
    "email",
    "resume_url",
    "github_url",
    "linkedin_url",
    "portfolio_url",
    "cgpa",
    "academic_year",
    "custom_fields",
    "raw_data",
    "field_statuses",
}


class MemberSchema(BaseModel):
    """A single team member from the registration data.

    Required core structural fields: member_id, name.
    Recognized optional fields: email, resume_url, github_url, linkedin_url,
    portfolio_url, cgpa, academic_year.
    Arbitrary custom form fields are preserved in `custom_fields`.
    The exact original record is preserved in `raw_data`.
    """

    member_id: str = Field(..., min_length=1, description="Unique member identifier")
    name: str = Field(..., min_length=1, description="Member's display name")

    # Standard recognized optional profile fields
    email: Optional[str] = Field(None, description="Email address (optional)")
    resume_url: Optional[str] = Field(None, description="Resume URL (optional)")
    github_url: Optional[str] = Field(None, description="GitHub profile URL (optional)")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn profile URL (optional)")
    portfolio_url: Optional[str] = Field(None, description="Portfolio URL (optional)")
    cgpa: Optional[str] = Field(None, description="CGPA / GPA metric (optional)")
    academic_year: Optional[str] = Field(None, description="Academic year / batch (optional)")

    # Dynamic & raw data preservation
    custom_fields: dict[str, Any] = Field(
        default_factory=dict,
        description="Preserved custom fields from the registration form",
    )
    raw_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Exact raw record as supplied by the organizer before mapping",
    )
    field_statuses: dict[str, FieldPresenceStatus] = Field(
        default_factory=dict,
        description="Explicit presence status per field (present, collected_blank, not_collected, invalid)",
    )

    # -- model validators ---------------------------------------------------

    @model_validator(mode="before")
    @classmethod
    def capture_custom_and_raw(cls, data: Any) -> Any:
        """Capture unrecognized fields into `custom_fields` and retain `raw_data`."""
        if isinstance(data, dict):
            raw = data.get("raw_data")
            if raw is None:
                raw = dict(data)
            custom = dict(data.get("custom_fields", {}))
            for k, v in list(data.items()):
                if k not in KNOWN_MEMBER_FIELDS:
                    custom[k] = v
            cleaned = {k: v for k, v in data.items() if k in KNOWN_MEMBER_FIELDS}
            cleaned["custom_fields"] = custom
            cleaned["raw_data"] = raw
            return cleaned
        return data

    # -- field validators ---------------------------------------------------

    @field_validator("member_id", "name", mode="before")
    @classmethod
    def strip_whitespace_required(cls, v: object) -> object:
        """Trim leading/trailing whitespace on required text fields."""
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator(
        "email",
        "resume_url",
        "github_url",
        "linkedin_url",
        "portfolio_url",
        "cgpa",
        "academic_year",
        mode="before",
    )
    @classmethod
    def strip_whitespace_optional(cls, v: object) -> object:
        """Trim whitespace on optional fields; treat blank strings as None."""
        if isinstance(v, str):
            v = v.strip()
            if v == "":
                return None
        return v

    @field_validator("email", mode="after")
    @classmethod
    def validate_email_format(cls, v: Optional[str]) -> Optional[str]:
        """Basic email validation — must contain '@' if provided."""
        if v is not None and "@" not in v:
            raise ValueError(f"Invalid email format: '{v}'")
        return v


# ---------------------------------------------------------------------------
# Team schema
# ---------------------------------------------------------------------------


KNOWN_TEAM_FIELDS = {
    "team_id",
    "team_name",
    "members",
    "custom_fields",
    "raw_data",
    "is_temporary_id",
    "is_unresolved",
    "duplicate_name_detected",
}


class TeamSchema(BaseModel):
    """A team consisting of one or more members, with custom fields preserved."""

    team_id: str = Field(..., min_length=1, description="Unique team identifier")
    team_name: str = Field(..., min_length=1, description="Team display name")
    members: list[MemberSchema] = Field(
        ..., min_length=1, description="At least one member required"
    )

    # Duplicate detection & temporary ID flags
    is_temporary_id: bool = Field(
        default=False,
        description="Whether this team was assigned a temporary ID due to missing/ambiguous ID",
    )
    is_unresolved: bool = Field(
        default=False,
        description="Whether this team's identity is unresolved due to duplicate names or ambiguous registration",
    )
    duplicate_name_detected: bool = Field(
        default=False,
        description="Whether another registration with the same normalized team name was detected",
    )

    # Dynamic & raw data preservation
    custom_fields: dict[str, Any] = Field(
        default_factory=dict,
        description="Preserved team-level custom attributes",
    )
    raw_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw team-level data before mapping",
    )

    @model_validator(mode="before")
    @classmethod
    def capture_team_custom_and_raw(cls, data: Any) -> Any:
        """Capture unrecognized team attributes into `custom_fields` and retain `raw_data`."""
        if isinstance(data, dict):
            raw = data.get("raw_data")
            if raw is None:
                raw = {k: v for k, v in data.items() if k != "members"}
            custom = dict(data.get("custom_fields", {}))
            for k, v in list(data.items()):
                if k not in KNOWN_TEAM_FIELDS:
                    custom[k] = v
            cleaned = {k: v for k, v in data.items() if k in KNOWN_TEAM_FIELDS}
            cleaned["custom_fields"] = custom
            cleaned["raw_data"] = raw
            return cleaned
        return data

    @field_validator("team_id", "team_name", mode="before")
    @classmethod
    def strip_whitespace(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v


# ---------------------------------------------------------------------------
# Warning / Error detail schemas
# ---------------------------------------------------------------------------


class ValidationWarning(BaseModel):
    """A non-fatal warning (e.g. missing optional profile link, duplicate team name)."""

    team_id: str
    member_id: str = Field(
        default="",
        description="Member identifier if warning is member-specific, or empty string for team-level warnings",
    )
    field: str
    message: str


class ValidationError(BaseModel):
    """A fatal validation error for a specific record."""

    location: str = Field(
        ..., description="Where the error occurred (e.g. 'row 3' or 'team T1')"
    )
    message: str


# ---------------------------------------------------------------------------
# Upload response
# ---------------------------------------------------------------------------


class UploadResponse(BaseModel):
    """Structured response returned by POST /api/ingestion/upload."""

    success: bool
    teams_count: int = 0
    members_count: int = 0
    teams: list[TeamSchema] = Field(default_factory=list)
    warnings: list[ValidationWarning] = Field(default_factory=list)
    errors: list[ValidationError] = Field(default_factory=list)
    unmapped_fields: list[str] = Field(
        default_factory=list,
        description="Discovered fields retained as custom fields without canonical mapping",
    )
    dataset_id: Optional[str] = Field(
        default=None,
        description="Dataset identifier for persistent storage (populated when saved).",
    )


# ---------------------------------------------------------------------------
# Dataset persistence record
# ---------------------------------------------------------------------------


class DatasetRecord(BaseModel):
    """Persisted registration dataset record with upload metadata and parsed payload."""

    dataset_id: str = Field(..., min_length=1, description="Unique dataset identifier")
    filename: str = Field(..., description="Original upload filename")
    file_type: str = Field(..., description="File format type ('csv' or 'json')")
    teams_count: int = Field(0, description="Total number of teams in dataset")
    members_count: int = Field(0, description="Total number of members across teams")
    uploaded_at: Union[str, datetime.datetime] = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="ISO 8601 upload timestamp",
    )
    mapping: Optional[dict[str, Any]] = Field(None, description="Applied column mapping dictionary")
    warnings: list[Any] = Field(default_factory=list, description="Validation warnings from ingestion")
    unmapped_fields: list[Any] = Field(default_factory=list, description="Custom fields retained unmapped")
    created_at: Optional[Union[str, datetime.datetime]] = Field(None, description="ISO 8601 database persistence timestamp")
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Full parsed UploadResponse payload including teams structure",
    )

    @field_validator("uploaded_at", "created_at", mode="before")
    @classmethod
    def _coerce_dt_to_iso(cls, val: Any) -> Any:
        if isinstance(val, (datetime.datetime, datetime.date)):
            return val.isoformat()
        return val

