"""Pydantic schemas for registration data ingestion.

Defines the data structures for team members, teams, and the
upload response. All schemas use Pydantic v2 conventions.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Member schema
# ---------------------------------------------------------------------------
class MemberSchema(BaseModel):
    """A single team member from the registration data.

    Required fields: member_id, name.
    All profile-link fields are optional and may be absent or None.
    """

    member_id: str = Field(..., min_length=1, description="Unique member identifier")
    name: str = Field(..., min_length=1, description="Member's display name")
    email: Optional[str] = Field(None, description="Email address (optional)")
    resume_url: Optional[str] = Field(None, description="Resume URL (optional)")
    github_url: Optional[str] = Field(None, description="GitHub profile URL (optional)")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn profile URL (optional)")
    portfolio_url: Optional[str] = Field(None, description="Portfolio URL (optional)")

    # -- validators --------------------------------------------------------

    @field_validator("member_id", "name", mode="before")
    @classmethod
    def strip_whitespace_required(cls, v: object) -> object:
        """Trim leading/trailing whitespace on required text fields."""
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator(
        "email", "resume_url", "github_url", "linkedin_url", "portfolio_url",
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
class TeamSchema(BaseModel):
    """A team consisting of one or more members."""

    team_id: str = Field(..., min_length=1, description="Unique team identifier")
    team_name: str = Field(..., min_length=1, description="Team display name")
    members: list[MemberSchema] = Field(
        ..., min_length=1, description="At least one member required"
    )

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
    """A non-fatal warning (e.g. missing optional profile link)."""

    team_id: str
    member_id: str
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
