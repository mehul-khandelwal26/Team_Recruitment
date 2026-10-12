"""CSV and JSON file parsing for dynamic registration data.

Converts raw uploaded file bytes into validated team structures,
preserving custom/unmapped fields, tracking field presence states,
and supporting configurable field mappings.
"""

from __future__ import annotations

import io
import json
from typing import Any, Optional

import pandas as pd
from pydantic import ValidationError as PydanticValidationError

from app.schemas.ingestion import (
    FieldPresenceStatus,
    MemberSchema,
    TeamSchema,
    UploadResponse,
    ValidationError,
    ValidationWarning,
)

# Profile-link fields that are optional. Used to generate non-fatal warnings
# when a member is missing one or more of them.
_OPTIONAL_PROFILE_FIELDS = [
    "email",
    "resume_url",
    "github_url",
    "linkedin_url",
    "portfolio_url",
]

# Recognized standard member columns that map directly to MemberSchema fields
_RECOGNIZED_MEMBER_COLUMNS = {
    "member_id",
    "name",
    "email",
    "resume_url",
    "github_url",
    "linkedin_url",
    "portfolio_url",
    "cgpa",
    "academic_year",
}

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


def parse_csv(
    raw_bytes: bytes,
    mapping: Optional[dict[str, str]] = None,
) -> UploadResponse:
    """Parse a CSV file (one row per member) into teams with custom field preservation.

    Supports optional explicit field mapping from original column names to
    canonical fields. Unmapped columns are safely retained in ``custom_fields``
    and ``raw_data``.
    """
    errors: list[ValidationError] = []
    warnings: list[ValidationWarning] = []

    text = raw_bytes.decode("utf-8-sig", errors="replace").strip()
    if not text:
        return UploadResponse(
            success=False,
            errors=[ValidationError(location="file", message="Uploaded CSV file is empty.")],
        )

    # Read into a DataFrame
    try:
        df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    except Exception as exc:
        return UploadResponse(
            success=False,
            errors=[ValidationError(location="file", message=f"Failed to parse CSV: {exc}")],
        )

    # Store original column names for custom fields preservation
    original_columns = [str(c) for c in df.columns]

    # Apply mapping if provided, or default canonical normalization
    normalized_mapping: dict[str, str] = {}
    if mapping:
        # Validate that multiple columns don't map to the same target
        target_counts: dict[str, list[str]] = {}
        for src, tgt in mapping.items():
            tgt_norm = tgt.strip().lower()
            if tgt_norm == "member_name":
                tgt_norm = "name"
            target_counts.setdefault(tgt_norm, []).append(src)
        for tgt, srcs in target_counts.items():
            if len(srcs) > 1 and tgt in _REQUIRED_CSV_COLUMNS:
                errors.append(
                    ValidationError(
                        location="mapping",
                        message=f"Multiple columns mapped to required field '{tgt}': {', '.join(srcs)}",
                    )
                )
        if errors:
            return UploadResponse(success=False, errors=errors)

        # Normalize keys in mapping
        for src, tgt in mapping.items():
            tgt_norm = tgt.strip().lower()
            if tgt_norm == "member_name":
                tgt_norm = "name"
            normalized_mapping[src.strip().lower()] = tgt_norm

    # Build effective column mapping for DataFrame
    effective_cols: list[str] = []
    for col in original_columns:
        col_lower = col.strip().lower()
        if col_lower in normalized_mapping:
            effective_cols.append(normalized_mapping[col_lower])
        elif col in mapping if mapping else False:
            effective_cols.append(mapping[col].strip().lower())
        else:
            # Default alias check if member_name used without mapping
            if col_lower == "member_name":
                effective_cols.append("name")
            else:
                effective_cols.append(col_lower)

    df.columns = effective_cols

    # Check required structural columns
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

    # Track which columns are unmapped custom fields
    unmapped_fields = [
        original_columns[i]
        for i, col in enumerate(df.columns)
        if col not in _RECOGNIZED_MEMBER_COLUMNS and col not in {"team_id", "team_name"}
    ]

    # Row-level processing and grouping
    team_rows: dict[str, list[dict[str, Any]]] = {}
    team_names: dict[str, str] = {}

    for row_idx, row in df.iterrows():
        row_num = int(row_idx) + 2  # 1-indexed, +1 for header
        row_dict = row.to_dict()

        team_id = str(row_dict.get("team_id", "")).strip()
        team_name = str(row_dict.get("team_name", "")).strip()

        if not team_id:
            errors.append(
                ValidationError(location=f"row {row_num}", message="team_id is missing or empty.")
            )
            continue
        if not team_name:
            errors.append(
                ValidationError(location=f"row {row_num}", message="team_name is missing or empty.")
            )
            continue

        member_id = str(row_dict.get("member_id", "")).strip()
        name = str(row_dict.get("name", "")).strip()

        if not member_id:
            errors.append(
                ValidationError(location=f"row {row_num}", message="member_id is missing or empty.")
            )
            continue
        if not name:
            errors.append(
                ValidationError(location=f"row {row_num}", message="name is missing or empty.")
            )
            continue

        # Inconsistent team_name check
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

        # Construct member data dictionary
        # Preserve original row values in raw_data
        raw_row_data = {original_columns[i]: row.iloc[i] for i in range(len(original_columns))}
        custom_fields: dict[str, Any] = {}
        field_statuses: dict[str, FieldPresenceStatus] = {
            "team_id": FieldPresenceStatus.PRESENT,
            "team_name": FieldPresenceStatus.PRESENT,
            "member_id": FieldPresenceStatus.PRESENT,
            "name": FieldPresenceStatus.PRESENT,
        }

        member_data: dict[str, Any] = {
            "member_id": member_id,
            "name": name,
            "custom_fields": custom_fields,
            "raw_data": raw_row_data,
            "field_statuses": field_statuses,
        }

        # Profile link fields
        for field in _OPTIONAL_PROFILE_FIELDS:
            if field in row_dict:
                val = str(row_dict[field]).strip()
                if val:
                    member_data[field] = val
                    field_statuses[field] = FieldPresenceStatus.PRESENT
                else:
                    member_data[field] = None
                    field_statuses[field] = FieldPresenceStatus.COLLECTED_BLANK
            else:
                member_data[field] = None
                field_statuses[field] = FieldPresenceStatus.NOT_COLLECTED

        # Additional recognized fields (cgpa, academic_year)
        for field in ["cgpa", "academic_year"]:
            if field in row_dict:
                val = str(row_dict[field]).strip()
                if val:
                    member_data[field] = val
                    field_statuses[field] = FieldPresenceStatus.PRESENT
                else:
                    member_data[field] = None
                    field_statuses[field] = FieldPresenceStatus.COLLECTED_BLANK
            else:
                member_data[field] = None
                field_statuses[field] = FieldPresenceStatus.NOT_COLLECTED

        # Extract arbitrary custom fields
        for i, col in enumerate(df.columns):
            if col not in _RECOGNIZED_MEMBER_COLUMNS and col not in {"team_id", "team_name"}:
                orig_name = original_columns[i]
                raw_val = row.iloc[i]
                val = str(raw_val).strip() if raw_val is not None else ""
                custom_fields[orig_name] = val if val else None
                if val:
                    field_statuses[orig_name] = FieldPresenceStatus.PRESENT
                else:
                    field_statuses[orig_name] = FieldPresenceStatus.COLLECTED_BLANK

        team_rows.setdefault(team_id, []).append(member_data)

    # Build & validate teams
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
        unmapped_fields=unmapped_fields,
    )


def parse_json(
    raw_bytes: bytes,
    mapping: Optional[dict[str, str]] = None,
) -> UploadResponse:
    """Parse a JSON file (array of team objects) into teams with custom field preservation.

    Supports optional explicit field mapping. Arbitrary team and member
    attributes are preserved in ``custom_fields`` and ``raw_data``.
    """
    errors: list[ValidationError] = []
    warnings: list[ValidationWarning] = []

    text = raw_bytes.decode("utf-8-sig", errors="replace").strip()
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
            errors=[
                ValidationError(
                    location="file",
                    message="JSON root must be an array of team objects.",
                )
            ],
        )

    if len(data) == 0:
        return UploadResponse(
            success=False,
            errors=[
                ValidationError(
                    location="file",
                    message="JSON array is empty – no teams found.",
                )
            ],
        )

    # Apply mapping if provided
    norm_mapping = {}
    if mapping:
        for k, v in mapping.items():
            tgt = v.strip().lower()
            if tgt == "member_name":
                tgt = "name"
            norm_mapping[k.strip().lower()] = tgt

    teams: list[TeamSchema] = []
    discovered_unmapped: set[str] = set()

    for idx, raw_team_obj in enumerate(data):
        loc = f"team index {idx}"
        if not isinstance(raw_team_obj, dict):
            errors.append(
                ValidationError(location=loc, message="Each team entry must be a JSON object.")
            )
            continue

        # Remap team object keys if mapping provided
        team_obj = _apply_json_mapping(raw_team_obj, norm_mapping)

        # Track unmapped team keys
        for k in team_obj.keys():
            if k not in {"team_id", "team_name", "members", "custom_fields", "raw_data"}:
                discovered_unmapped.add(k)

        # Process members array
        members_raw = team_obj.get("members")
        if not isinstance(members_raw, list):
            errors.append(
                ValidationError(location=loc, message="members field must be an array.")
            )
            continue

        if len(members_raw) == 0:
            errors.append(
                ValidationError(
                    location=loc,
                    message="members: List should have at least 1 item after validation, not 0",
                )
            )
            continue

        processed_members = []
        member_had_error = False

        for m_idx, raw_m in enumerate(members_raw):
            m_loc = f"{loc}, member index {m_idx}"
            if not isinstance(raw_m, dict):
                errors.append(
                    ValidationError(location=m_loc, message="Member entry must be a JSON object.")
                )
                member_had_error = True
                continue

            m_obj = _apply_json_mapping(raw_m, norm_mapping)
            if "member_name" in m_obj and "name" not in m_obj:
                m_obj["name"] = m_obj.pop("member_name")

            # Track unmapped member keys
            for k in m_obj.keys():
                if k not in _RECOGNIZED_MEMBER_COLUMNS and k not in {"custom_fields", "raw_data", "field_statuses"}:
                    discovered_unmapped.add(k)

            # Build field_statuses
            field_statuses = {}
            for field in _OPTIONAL_PROFILE_FIELDS:
                if field in m_obj:
                    val = m_obj[field]
                    if val is not None and str(val).strip():
                        field_statuses[field] = FieldPresenceStatus.PRESENT
                    else:
                        field_statuses[field] = FieldPresenceStatus.COLLECTED_BLANK
                else:
                    field_statuses[field] = FieldPresenceStatus.NOT_COLLECTED
            m_obj["field_statuses"] = field_statuses

            try:
                member_model = MemberSchema.model_validate(m_obj)
                processed_members.append(member_model)
            except PydanticValidationError as exc:
                member_had_error = True
                for err in exc.errors():
                    field_path = " → ".join(str(p) for p in err["loc"])
                    errors.append(
                        ValidationError(location=loc, message=f"{field_path}: {err['msg']}")
                    )

        if member_had_error:
            continue

        team_obj["members"] = processed_members

        try:
            team = TeamSchema.model_validate(team_obj)
        except PydanticValidationError as exc:
            for err in exc.errors():
                field_path = " → ".join(str(p) for p in err["loc"])
                errors.append(
                    ValidationError(location=loc, message=f"{field_path}: {err['msg']}")
                )
            continue

        dup_err = _check_duplicate_members(team)
        if dup_err:
            errors.append(ValidationError(location=loc, message=dup_err))
            continue

        warnings.extend(_missing_profile_warnings(team))
        teams.append(team)

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
        unmapped_fields=sorted(discovered_unmapped),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _apply_json_mapping(obj: dict[str, Any], norm_mapping: dict[str, str]) -> dict[str, Any]:
    """Remap keys of a dictionary using normalized target field mapping."""
    if not norm_mapping:
        return dict(obj)
    mapped: dict[str, Any] = {}
    for k, v in obj.items():
        k_lower = k.strip().lower()
        target_key = norm_mapping.get(k_lower, k)
        mapped[target_key] = v
    return mapped


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

        team = TeamSchema(team_id=team_id, team_name=team_name, members=valid_members)

        dup_err = _check_duplicate_members(team)
        if dup_err:
            errors.append(ValidationError(location=f"team '{team_id}'", message=dup_err))
            continue

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
            value = getattr(member, field, None)
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
