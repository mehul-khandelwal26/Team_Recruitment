"""CSV and JSON file parsing for registration data.

Converts raw uploaded file bytes into validated team structures,
collecting errors and warnings along the way.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any

import pandas as pd
from pydantic import ValidationError as PydanticValidationError

from app.schemas.ingestion import (
    MemberSchema,
    TeamSchema,
    UploadResponse,
    ValidationError,
    ValidationWarning,
)

# Profile-link fields that are optional.  Used to generate warnings
# when a member is missing one or more of them.
_OPTIONAL_PROFILE_FIELDS = [
    "email",
    "resume_url",
    "github_url",
    "linkedin_url",
    "portfolio_url",
]

# Required columns for CSV uploads (order-insensitive)
_REQUIRED_CSV_COLUMNS = {
    "team_id",
    "team_name",
    "member_id",
    "name",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_csv(raw_bytes: bytes) -> UploadResponse:
    """Parse a CSV file (one row per member) into teams.

    Expected columns:
        team_id, team_name, member_id, name,
        email, resume_url, github_url, linkedin_url, portfolio_url

    Rows sharing the same ``team_id`` are grouped into a single team.
    """
    errors: list[ValidationError] = []
    warnings: list[ValidationWarning] = []

    text = raw_bytes.decode("utf-8-sig").strip()  # handle BOM
    if not text:
        return UploadResponse(
            success=False,
            errors=[ValidationError(location="file", message="Uploaded CSV file is empty.")],
        )

    # -- Read into a DataFrame for convenient grouping ---------------------
    try:
        df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    except Exception as exc:
        return UploadResponse(
            success=False,
            errors=[ValidationError(location="file", message=f"Failed to parse CSV: {exc}")],
        )

    # Normalise column names: lowercase + strip whitespace
    df.columns = [c.strip().lower() for c in df.columns]

    # -- Check required columns --------------------------------------------
    missing_cols = _REQUIRED_CSV_COLUMNS - set(df.columns)
    if missing_cols:
        return UploadResponse(
            success=False,
            errors=[
                ValidationError(
                    location="file",
                    message=f"Missing required CSV column(s): {', '.join(sorted(missing_cols))}",
                )
            ],
        )

    # -- Row-level validation ----------------------------------------------
    # Collect raw member dicts keyed by team_id
    team_rows: dict[str, list[dict[str, Any]]] = {}
    team_names: dict[str, str] = {}  # first team_name seen per team_id

    for row_idx, row in df.iterrows():
        row_num = int(row_idx) + 2  # 1-indexed, +1 for header
        row_dict = row.to_dict()

        team_id = str(row_dict.get("team_id", "")).strip()
        team_name = str(row_dict.get("team_name", "")).strip()

        # Basic required-field checks at row level
        if not team_id:
            errors.append(ValidationError(location=f"row {row_num}", message="team_id is missing or empty."))
            continue
        if not team_name:
            errors.append(ValidationError(location=f"row {row_num}", message="team_name is missing or empty."))
            continue

        member_id = str(row_dict.get("member_id", "")).strip()
        name = str(row_dict.get("name", "")).strip()

        if not member_id:
            errors.append(ValidationError(location=f"row {row_num}", message="member_id is missing or empty."))
            continue
        if not name:
            errors.append(ValidationError(location=f"row {row_num}", message="name is missing or empty."))
            continue

        # Check for inconsistent team_name
        if team_id in team_names:
            if team_names[team_id] != team_name:
                errors.append(
                    ValidationError(
                        location=f"row {row_num}",
                        message=(
                            f"Inconsistent team_name for team_id '{team_id}': "
                            f"previously '{team_names[team_id]}', now '{team_name}'."
                        ),
                    )
                )
                continue
        else:
            team_names[team_id] = team_name

        # Build member dict (only include columns present in the CSV)
        member_data: dict[str, Any] = {
            "member_id": member_id,
            "name": name,
        }
        for field in _OPTIONAL_PROFILE_FIELDS:
            if field in row_dict:
                val = str(row_dict[field]).strip()
                member_data[field] = val if val else None
            # If the column doesn't exist at all, leave it absent → schema default (None)

        team_rows.setdefault(team_id, []).append(member_data)

    # -- Build & validate teams -------------------------------------------
    teams, team_errors, team_warnings = _build_teams(team_rows, team_names)
    errors.extend(team_errors)
    warnings.extend(team_warnings)

    success = len(teams) > 0 and len(errors) == 0
    members_count = sum(len(t.members) for t in teams)

    return UploadResponse(
        success=success,
        teams_count=len(teams),
        members_count=members_count,
        teams=teams,
        warnings=warnings,
        errors=errors,
    )


def parse_json(raw_bytes: bytes) -> UploadResponse:
    """Parse a JSON file (array of team objects) into teams.

    Expected format::

        [
          {
            "team_id": "...",
            "team_name": "...",
            "members": [
              { "member_id": "...", "name": "...", ... },
              ...
            ]
          },
          ...
        ]
    """
    errors: list[ValidationError] = []
    warnings: list[ValidationWarning] = []

    text = raw_bytes.decode("utf-8-sig").strip()
    if not text:
        return UploadResponse(
            success=False,
            errors=[ValidationError(location="file", message="Uploaded JSON file is empty.")],
        )

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return UploadResponse(
            success=False,
            errors=[ValidationError(location="file", message=f"Malformed JSON: {exc}")],
        )

    if not isinstance(data, list):
        return UploadResponse(
            success=False,
            errors=[ValidationError(location="file", message="JSON root must be an array of team objects.")],
        )

    if len(data) == 0:
        return UploadResponse(
            success=False,
            errors=[ValidationError(location="file", message="JSON array is empty – no teams found.")],
        )

    # -- Validate each team object ----------------------------------------
    teams: list[TeamSchema] = []
    for idx, team_obj in enumerate(data):
        loc = f"team index {idx}"
        if not isinstance(team_obj, dict):
            errors.append(ValidationError(location=loc, message="Each team entry must be a JSON object."))
            continue

        try:
            team = TeamSchema.model_validate(team_obj)
        except PydanticValidationError as exc:
            for err in exc.errors():
                field_path = " → ".join(str(p) for p in err["loc"])
                errors.append(
                    ValidationError(location=loc, message=f"{field_path}: {err['msg']}")
                )
            continue

        # Duplicate member_id check within this team
        dup_err = _check_duplicate_members(team)
        if dup_err:
            errors.append(ValidationError(location=loc, message=dup_err))
            continue

        # Missing-profile warnings
        warnings.extend(_missing_profile_warnings(team))
        teams.append(team)

    # Duplicate team_id check across all validated teams
    team_id_errors = _check_duplicate_team_ids(teams)
    errors.extend(team_id_errors)

    success = len(teams) > 0 and len(errors) == 0
    members_count = sum(len(t.members) for t in teams)

    return UploadResponse(
        success=success,
        teams_count=len(teams),
        members_count=members_count,
        teams=teams,
        warnings=warnings,
        errors=errors,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_teams(
    team_rows: dict[str, list[dict[str, Any]]],
    team_names: dict[str, str],
) -> tuple[list[TeamSchema], list[ValidationError], list[ValidationWarning]]:
    """Validate grouped rows into TeamSchema objects."""
    teams: list[TeamSchema] = []
    errors: list[ValidationError] = []
    warnings: list[ValidationWarning] = []

    for team_id, members_data in team_rows.items():
        team_name = team_names[team_id]

        # Validate individual members via Pydantic
        valid_members: list[MemberSchema] = []
        for m in members_data:
            try:
                member = MemberSchema.model_validate(m)
                valid_members.append(member)
            except PydanticValidationError as exc:
                for err in exc.errors():
                    field_path = " → ".join(str(p) for p in err["loc"])
                    errors.append(
                        ValidationError(
                            location=f"team '{team_id}', member_id '{m.get('member_id', '?')}'",
                            message=f"{field_path}: {err['msg']}",
                        )
                    )

        if not valid_members:
            errors.append(
                ValidationError(
                    location=f"team '{team_id}'",
                    message="No valid members after validation.",
                )
            )
            continue

        # Build team
        team = TeamSchema(team_id=team_id, team_name=team_name, members=valid_members)

        # Duplicate member_id check
        dup_err = _check_duplicate_members(team)
        if dup_err:
            errors.append(ValidationError(location=f"team '{team_id}'", message=dup_err))
            continue

        # Missing-profile warnings
        warnings.extend(_missing_profile_warnings(team))
        teams.append(team)

    return teams, errors, warnings


def _check_duplicate_members(team: TeamSchema) -> str | None:
    """Return an error message if duplicate member_ids exist, else None."""
    seen: set[str] = set()
    duplicates: list[str] = []
    for m in team.members:
        if m.member_id in seen:
            duplicates.append(m.member_id)
        seen.add(m.member_id)
    if duplicates:
        return f"Duplicate member_id(s) within team: {', '.join(duplicates)}"
    return None


def _check_duplicate_team_ids(teams: list[TeamSchema]) -> list[ValidationError]:
    """Check for duplicate team_ids across all teams."""
    seen: set[str] = set()
    errors: list[ValidationError] = []
    for t in teams:
        if t.team_id in seen:
            errors.append(
                ValidationError(
                    location=f"team '{t.team_id}'",
                    message=f"Duplicate team_id '{t.team_id}' found.",
                )
            )
        seen.add(t.team_id)
    return errors


def _missing_profile_warnings(team: TeamSchema) -> list[ValidationWarning]:
    """Generate warnings for members who have missing optional profile fields."""
    warns: list[ValidationWarning] = []
    for member in team.members:
        for field in _OPTIONAL_PROFILE_FIELDS:
            value = getattr(member, field)
            if value is None:
                warns.append(
                    ValidationWarning(
                        team_id=team.team_id,
                        member_id=member.member_id,
                        field=field,
                        message=f"Member '{member.name}' is missing '{field}'.",
                    )
                )
    return warns
