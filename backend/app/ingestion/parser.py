"""CSV and JSON file parsing for dynamic registration data.

Converts raw uploaded file bytes into validated team structures,
preserving custom/unmapped fields, tracking field presence states,
and supporting configurable field mappings.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import zipfile
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
from app.signals.resume import extract_text_from_document

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

_REQUIRED_CSV_COLUMNS = {"team_name", "name"}

# Recognized structural fields for hierarchy construction
_STRUCTURAL_FIELDS = {
    "team_id",
    "team_name",
    "member_id",
    "name",
}


def normalize_team_name(name: str) -> str:
    """Normalize a team name for duplicate detection.

    Converts to lowercase, collapses consecutive punctuation and whitespace
    into single spaces, and trims.
    Example: '  Code Warriors! ' -> 'code warriors', 'Code_Warriors' -> 'code warriors'.
    """
    cleaned = re.sub(r"[_\W]+", " ", name.strip().lower()).strip()
    return cleaned if cleaned else name.strip().lower()


def generate_stable_team_id(team_name: str) -> str:
    """Generate a deterministic, stable team_id from team_name.

    Stability guarantee: Uses a URL-safe slugified version of team_name combined
    with a deterministic SHA-256 hash prefix (8 hex chars). Identical team names
    in repeated runs produce identical team_ids without randomness.
    """
    cleaned = team_name.strip()
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", cleaned.lower()).strip("_")
    slug = slug[:24] if slug else "team"
    h = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:8]
    return f"team_{slug}_{h}"


def generate_temporary_team_id(team_name: str, occurrence: int) -> str:
    """Generate a distinct temporary Team ID for ambiguous duplicate teams.

    Format: temp_team_{slug}_{hash}_unresolved_{occurrence}

    - Distinct prefix 'temp_team_' prominently identifies temporary status.
    - Suffix '_unresolved_{occurrence}' marks unresolved ambiguity and ensures
      uniqueness among competing teams sharing the same name.
    - Deterministic across identical file uploads with consistent record order.
    Limitations across repeat uploads: If new registrations are inserted or reordered,
    occurrence numbers may shift. Distinct teams sharing identical names cannot guarantee
    cross-upload stability without explicit IDs or registration timestamps.
    """
    cleaned = team_name.strip()
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", cleaned.lower()).strip("_")
    slug = slug[:24] if slug else "team"
    h = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:6]
    return f"temp_team_{slug}_{h}_unresolved_{occurrence}"


def generate_stable_member_id(team_id: str, member_idx: int) -> str:
    """Generate a deterministic, stable member_id scoped to the team.

    Stability guarantee: Formed by combining the team_id with a 1-based member index
    relative to the team order within the upload (e.g. `team_alpha_1a2b3c4d_m1`).
    This guarantees uniqueness even if participants share identical names, and
    is completely deterministic across re-runs on the same file.
    """
    return f"{team_id}_m{member_idx}"


def _format_row_ranges(rows: list[int]) -> str:
    """Format row numbers into human-readable ranges, e.g. 'rows 2-3', 'row 5'."""
    if not rows:
        return ""
    sorted_rows = sorted(set(rows))
    ranges: list[str] = []
    start = sorted_rows[0]
    prev = sorted_rows[0]
    for r in sorted_rows[1:]:
        if r == prev + 1:
            prev = r
        else:
            ranges.append(f"{start}-{prev}" if start != prev else f"{start}")
            start = r
            prev = r
    ranges.append(f"{start}-{prev}" if start != prev else f"{start}")
    s = ", ".join(ranges)
    return f"row {s}" if len(sorted_rows) == 1 else f"rows {s}"


class _TeamMeta:
    """Internal metadata describing a team registration block."""

    def __init__(
        self,
        team_id: str,
        team_name: str,
        is_temporary_id: bool = False,
        is_unresolved: bool = False,
        duplicate_name_detected: bool = False,
        custom_fields: Optional[dict[str, Any]] = None,
        raw_data: Optional[dict[str, Any]] = None,
    ) -> None:
        self.team_id = team_id
        self.team_name = team_name
        self.is_temporary_id = is_temporary_id
        self.is_unresolved = is_unresolved
        self.duplicate_name_detected = duplicate_name_detected
        self.custom_fields = custom_fields or {}
        self.raw_data = raw_data or {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------



def _process_resumes_archive(
    archive_bytes: bytes,
) -> tuple[dict[str, tuple[str, str]], list[ValidationWarning]]:
    """Unpack companion resumes ZIP archive and extract resume text.

    Returns:
        (resume_index, warnings):
        resume_index maps normalized keys (filename, basename, email, member_id, name)
        to (filename, extracted_text).
    """
    resume_index: dict[str, tuple[str, str]] = {}
    warnings: list[ValidationWarning] = []

    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes), "r") as zf:
            for info in zf.infolist():
                if info.is_dir() or info.filename.startswith("__MACOSX/") or "/." in info.filename:
                    continue
                clean_name = os.path.basename(info.filename)
                if not clean_name or clean_name.startswith("."):
                    continue

                ext = clean_name.lower().split(".")[-1]
                if ext not in {"pdf", "docx"}:
                    continue

                if info.file_size > 10 * 1024 * 1024:
                    warnings.append(
                        ValidationWarning(
                            team_id="",
                            member_id="",
                            field="resumes_archive",
                            message=f"Resume file '{clean_name}' exceeds 10MB limit and was skipped.",
                        )
                    )
                    continue

                raw_doc_bytes = zf.read(info)
                text, err, _ = extract_text_from_document(raw_doc_bytes, clean_name)
                if err or not text:
                    warnings.append(
                        ValidationWarning(
                            team_id="",
                            member_id="",
                            field="resumes_archive",
                            message=f"Could not extract text from '{clean_name}': {err or 'Empty document'}",
                        )
                    )
                    continue

                entry = (clean_name, text)
                resume_index[clean_name.lower()] = entry
                norm_full = info.filename.replace("\\", "/").lower()
                resume_index[norm_full] = entry
                base_no_ext = clean_name.rsplit(".", 1)[0].lower()
                resume_index[base_no_ext] = entry
                norm_base = re.sub(r"[_\W]+", " ", base_no_ext).strip()
                if norm_base:
                    resume_index[norm_base] = entry
                    resume_index[norm_base.replace(" ", "")] = entry

    except Exception as exc:
        warnings.append(
            ValidationWarning(
                team_id="",
                member_id="",
                field="resumes_archive",
                message=f"Failed to inspect resumes ZIP archive: {exc}",
            )
        )

    return resume_index, warnings


def _match_member_resume(
    member_data: dict[str, Any],
    resume_index: dict[str, tuple[str, str]],
) -> Optional[tuple[str, str]]:
    """Match a member record to a resume entry in the companion archive index."""
    if not resume_index:
        return None

    # 1. Explicit resume column
    for r_key in ("resume_url", "resume", "resume_file", "resume_path", "cv"):
        val = member_data.get(r_key)
        if not val and isinstance(member_data.get("custom_fields"), dict):
            val = member_data["custom_fields"].get(r_key)
        if val and isinstance(val, str):
            clean_val = val.strip().replace("\\", "/").lower()
            if clean_val in resume_index:
                return resume_index[clean_val]
            base = os.path.basename(clean_val)
            if base in resume_index:
                return resume_index[base]
            base_no_ext = base.rsplit(".", 1)[0]
            if base_no_ext in resume_index:
                return resume_index[base_no_ext]

    # 2. Email match
    email = member_data.get("email")
    if email and isinstance(email, str):
        em_clean = email.strip().lower()
        if em_clean in resume_index:
            return resume_index[em_clean]
        for ext in (".pdf", ".docx"):
            if em_clean + ext in resume_index:
                return resume_index[em_clean + ext]

    # 3. Member ID / Roll Number match
    member_id = member_data.get("member_id")
    if member_id and isinstance(member_id, str):
        mid_clean = member_id.strip().lower()
        if mid_clean in resume_index:
            return resume_index[mid_clean]
        for ext in (".pdf", ".docx"):
            if mid_clean + ext in resume_index:
                return resume_index[mid_clean + ext]

    # 4. Name match
    name = member_data.get("name")
    if name and isinstance(name, str):
        n_clean = name.strip().lower()
        if n_clean in resume_index:
            return resume_index[n_clean]
        for ext in (".pdf", ".docx"):
            if n_clean + ext in resume_index:
                return resume_index[n_clean + ext]

        n_under = re.sub(r"\s+", "_", n_clean)
        if n_under in resume_index:
            return resume_index[n_under]
        for ext in (".pdf", ".docx"):
            if n_under + ext in resume_index:
                return resume_index[n_under + ext]

        n_condensed = re.sub(r"[\s_]+", "", n_clean)
        if n_condensed in resume_index:
            return resume_index[n_condensed]
        for ext in (".pdf", ".docx"):
            if n_condensed + ext in resume_index:
                return resume_index[n_condensed + ext]

    return None


def parse_csv(
    raw_bytes: bytes,
    mapping: Optional[dict[str, str]] = None,
    resumes_zip_bytes: Optional[bytes] = None,
) -> UploadResponse:
    """Parse a CSV file (one row per member) into teams with custom field preservation.

    Supports optional explicit field mapping from original column names to
    canonical fields. Unmapped columns are safely retained in ``custom_fields``
    and ``raw_data``.
    """
    errors: list[ValidationError] = []
    warnings: list[ValidationWarning] = []

    # Process optional companion resumes archive
    resume_index: dict[str, tuple[str, str]] = {}
    if resumes_zip_bytes:
        resume_index, zip_warnings = _process_resumes_archive(resumes_zip_bytes)
        warnings.extend(zip_warnings)
    matched_filenames: set[str] = set()

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
        # Validate that multiple columns don't map to the same target field
        target_counts: dict[str, list[str]] = {}
        for src, tgt in mapping.items():
            tgt_norm = tgt.strip().lower()
            if tgt_norm == "member_name":
                tgt_norm = "name"
            target_counts.setdefault(tgt_norm, []).append(src)
        for tgt, srcs in target_counts.items():
            if len(srcs) > 1:
                errors.append(
                    ValidationError(
                        location="mapping",
                        message=f"Multiple columns mapped to field '{tgt}': {', '.join(srcs)}",
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

    # Check required structural columns: team_name and name are required
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

    # Row-level processing and registration block partitioning
    blocks: list[dict[str, Any]] = []
    explicit_block_lookup: dict[str, int] = {}
    reg_block_lookup: dict[tuple[str, str], int] = {}
    current_anon_block_idx: Optional[int] = None
    last_anon_norm_name: Optional[str] = None

    for row_idx, row in df.iterrows():
        row_num = int(row_idx) + 2  # 1-indexed, +1 for header
        row_dict = row.to_dict()

        team_name = str(row_dict.get("team_name", "")).strip()
        if not team_name:
            errors.append(
                ValidationError(location=f"row {row_num}", message="team_name is missing or empty.")
            )
            continue

        name = str(row_dict.get("name", "")).strip()
        if not name:
            errors.append(
                ValidationError(location=f"row {row_num}", message="name is missing or empty.")
            )
            continue

        raw_team_id = str(row_dict.get("team_id", "")).strip() if "team_id" in row_dict else ""
        norm_name = normalize_team_name(team_name)
        reg_id = str(row_dict.get("registration_id") or row_dict.get("submission_id") or "").strip()

        # Decide block
        if raw_team_id:
            if raw_team_id in explicit_block_lookup:
                b_idx = explicit_block_lookup[raw_team_id]
                existing_team_name = blocks[b_idx]["team_name"]
                if existing_team_name != team_name:
                    errors.append(
                        ValidationError(
                            location=f"row {row_num}",
                            message=(
                                f"Inconsistent team_name for team_id '{raw_team_id}': "
                                f"previously '{existing_team_name}', now '{team_name}'."
                            ),
                        )
                    )
                    continue
                blocks[b_idx]["row_numbers"].append(row_num)
                blocks[b_idx]["row_records"].append((row_num, row_dict, row))
            else:
                b_idx = len(blocks)
                explicit_block_lookup[raw_team_id] = b_idx
                blocks.append({
                    "team_name": team_name,
                    "norm_name": norm_name,
                    "raw_team_id": raw_team_id,
                    "row_numbers": [row_num],
                    "row_records": [(row_num, row_dict, row)],
                })
            current_anon_block_idx = None
            last_anon_norm_name = None

        elif reg_id:
            reg_key = (norm_name, reg_id)
            if reg_key in reg_block_lookup:
                b_idx = reg_block_lookup[reg_key]
                blocks[b_idx]["row_numbers"].append(row_num)
                blocks[b_idx]["row_records"].append((row_num, row_dict, row))
            else:
                b_idx = len(blocks)
                reg_block_lookup[reg_key] = b_idx
                blocks.append({
                    "team_name": team_name,
                    "norm_name": norm_name,
                    "raw_team_id": "",
                    "row_numbers": [row_num],
                    "row_records": [(row_num, row_dict, row)],
                })
            current_anon_block_idx = None
            last_anon_norm_name = None

        else:
            # Contiguous grouping by normalized team name
            if current_anon_block_idx is not None and last_anon_norm_name == norm_name:
                blocks[current_anon_block_idx]["row_numbers"].append(row_num)
                blocks[current_anon_block_idx]["row_records"].append((row_num, row_dict, row))
            else:
                b_idx = len(blocks)
                current_anon_block_idx = b_idx
                last_anon_norm_name = norm_name
                blocks.append({
                    "team_name": team_name,
                    "norm_name": norm_name,
                    "raw_team_id": "",
                    "row_numbers": [row_num],
                    "row_records": [(row_num, row_dict, row)],
                })

    # Duplicate team name detection & ID assignment across blocks
    blocks_by_norm: dict[str, list[int]] = {}
    for i, blk in enumerate(blocks):
        blocks_by_norm.setdefault(blk["norm_name"], []).append(i)

    for norm_name, b_indices in blocks_by_norm.items():
        if len(b_indices) > 1:
            # Multiple registration blocks share the same normalized team name
            anon_counter = 0
            for b_idx in b_indices:
                blk = blocks[b_idx]
                blk["duplicate_name_detected"] = True
                if blk["raw_team_id"]:
                    blk["team_id"] = blk["raw_team_id"]
                    blk["is_temporary_id"] = False
                    blk["is_unresolved"] = False
                else:
                    anon_counter += 1
                    blk["team_id"] = generate_temporary_team_id(blk["team_name"], anon_counter)
                    blk["is_temporary_id"] = True
                    blk["is_unresolved"] = True
        else:
            # Exactly one block with this team name
            b_idx = b_indices[0]
            blk = blocks[b_idx]
            blk["duplicate_name_detected"] = False
            if blk["raw_team_id"]:
                blk["team_id"] = blk["raw_team_id"]
                blk["is_temporary_id"] = False
                blk["is_unresolved"] = False
            else:
                blk["team_id"] = generate_stable_team_id(blk["team_name"])
                blk["is_temporary_id"] = False
                blk["is_unresolved"] = False

    # Generate duplicate warnings
    for norm_name, b_indices in blocks_by_norm.items():
        if len(b_indices) > 1:
            all_locs = [_format_row_ranges(blocks[i]["row_numbers"]) for i in b_indices]
            all_locs_str = ", ".join(all_locs)
            all_ids = [blocks[i]["team_id"] for i in b_indices]

            for b_idx in b_indices:
                blk = blocks[b_idx]
                other_ids = [tid for tid in all_ids if tid != blk["team_id"]]
                other_ids_str = ", ".join(other_ids) if other_ids else "none"
                my_loc = _format_row_ranges(blk["row_numbers"])

                if blk["is_temporary_id"]:
                    msg = (
                        f"Duplicate team name '{blk['team_name']}' detected across multiple registration blocks "
                        f"({all_locs_str}). Assigned temporary unresolved ID '{blk['team_id']}' for {my_loc}. "
                        f"Conflicting team ID(s): {other_ids_str}."
                    )
                else:
                    msg = (
                        f"Duplicate team name '{blk['team_name']}' detected across multiple registration blocks "
                        f"({all_locs_str}). Preserved explicit ID '{blk['team_id']}' for {my_loc}. "
                        f"Conflicting team ID(s): {other_ids_str}."
                    )

                warnings.append(
                    ValidationWarning(
                        team_id=blk["team_id"],
                        member_id="",
                        field="team_name",
                        message=msg,
                    )
                )

    # Build member data structures per block
    team_rows: dict[str, list[dict[str, Any]]] = {}
    team_metas: dict[str, _TeamMeta] = {}

    for blk in blocks:
        team_id = blk["team_id"]
        team_name = blk["team_name"]
        team_metas[team_id] = _TeamMeta(
            team_id=team_id,
            team_name=team_name,
            is_temporary_id=blk["is_temporary_id"],
            is_unresolved=blk["is_unresolved"],
            duplicate_name_detected=blk["duplicate_name_detected"],
        )

        existing_m_ids: set[str] = set()
        member_counter = 0

        for row_num, row_dict, row in blk["row_records"]:
            raw_team_id = str(row_dict.get("team_id", "")).strip() if "team_id" in row_dict else ""
            raw_member_id = str(row_dict.get("member_id", "")).strip() if "member_id" in row_dict else ""
            name = str(row_dict.get("name", "")).strip()

            if raw_member_id:
                member_id = raw_member_id
            else:
                member_counter += 1
                member_id = generate_stable_member_id(team_id, member_counter)
                while member_id in existing_m_ids:
                    member_counter += 1
                    member_id = generate_stable_member_id(team_id, member_counter)
            existing_m_ids.add(member_id)

            # Construct member data dictionary
            # Preserve original row values in raw_data
            raw_row_data = {original_columns[i]: row.iloc[i] for i in range(len(original_columns))}
            custom_fields: dict[str, Any] = {}
            field_statuses: dict[str, FieldPresenceStatus] = {
                "team_name": FieldPresenceStatus.PRESENT,
                "name": FieldPresenceStatus.PRESENT,
            }

            if "team_id" in row_dict:
                field_statuses["team_id"] = (
                    FieldPresenceStatus.PRESENT if raw_team_id else FieldPresenceStatus.COLLECTED_BLANK
                )
            else:
                field_statuses["team_id"] = FieldPresenceStatus.NOT_COLLECTED

            if "member_id" in row_dict:
                field_statuses["member_id"] = (
                    FieldPresenceStatus.PRESENT if raw_member_id else FieldPresenceStatus.COLLECTED_BLANK
                )
            else:
                field_statuses["member_id"] = FieldPresenceStatus.NOT_COLLECTED

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

            if resume_index:
                matched_resume = _match_member_resume(member_data, resume_index)
                if matched_resume:
                    fname, ftext = matched_resume
                    custom_fields["resume_text"] = ftext
                    custom_fields["resume_filename"] = fname
                    field_statuses["resume_url"] = FieldPresenceStatus.PRESENT
                    if not member_data.get("resume_url"):
                        member_data["resume_url"] = f"zip://{fname}"
                    matched_filenames.add(fname.lower())
            team_rows.setdefault(team_id, []).append(member_data)

    # Build & validate teams
    teams, team_errors, team_warnings = _build_teams(team_rows, team_metas)
    errors.extend(team_errors)
    warnings.extend(team_warnings)

    team_id_errors = _check_duplicate_team_ids(teams)
    errors.extend(team_id_errors)

    disambig_warnings = _disambiguate_cross_team_member_ids(teams, warnings)
    warnings.extend(disambig_warnings)
    if resume_index:
        total_unique_resumes = len({fn.lower() for fn, _ in resume_index.values()})
        unmatched_count = total_unique_resumes - len(matched_filenames)
        if unmatched_count > 0:
            warnings.append(
                ValidationWarning(
                    team_id="",
                    member_id="",
                    field="resumes_archive",
                    message=f"Companion resumes ZIP contained {total_unique_resumes} resume(s); {len(matched_filenames)} matched candidates, and {unmatched_count} were unmatched.",
                )
            )
        else:
            warnings.append(
                ValidationWarning(
                    team_id="",
                    member_id="",
                    field="resumes_archive",
                    message=f"All {total_unique_resumes} resume(s) in companion ZIP successfully matched candidates.",
                )
            )

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
    resumes_zip_bytes: Optional[bytes] = None,
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
        target_counts: dict[str, list[str]] = {}
        for k, v in mapping.items():
            tgt = v.strip().lower()
            if tgt == "member_name":
                tgt = "name"
            target_counts.setdefault(tgt, []).append(k)
            norm_mapping[k.strip().lower()] = tgt
        for tgt, srcs in target_counts.items():
            if len(srcs) > 1:
                return UploadResponse(
                    success=False,
                    errors=[
                        ValidationError(
                            location="mapping",
                            message=f"Multiple fields mapped to field '{tgt}': {', '.join(srcs)}",
                        )
                    ],
                )

    teams: list[TeamSchema] = []
    discovered_unmapped: set[str] = set()
    resume_index: dict[str, tuple[str, str]] = {}
    if resumes_zip_bytes:
        resume_index, zip_warnings = _process_resumes_archive(resumes_zip_bytes)
        warnings.extend(zip_warnings)
    matched_filenames: set[str] = set()

    # Pass 1: Parse and validate JSON team objects
    team_entries: list[dict[str, Any]] = []
    norm_to_indices: dict[str, list[int]] = {}

    for idx, raw_team_obj in enumerate(data):
        loc = f"team index {idx}"
        if not isinstance(raw_team_obj, dict):
            errors.append(
                ValidationError(location=loc, message="Each team entry must be a JSON object.")
            )
            continue

        # Remap team object keys if mapping provided
        team_obj = _apply_json_mapping(raw_team_obj, norm_mapping)

        # Ensure team_name and raw_team_id
        raw_team_name = (
            str(team_obj.get("team_name", "")).strip()
            if "team_name" in team_obj and team_obj["team_name"] is not None
            else ""
        )
        raw_team_id = (
            str(team_obj.get("team_id", "")).strip()
            if "team_id" in team_obj and team_obj["team_id"] is not None
            else ""
        )

        if not raw_team_name and not raw_team_id:
            errors.append(
                ValidationError(location=loc, message="team_name is required.")
            )
            continue

        if not raw_team_name:
            raw_team_name = raw_team_id
            team_obj["team_name"] = raw_team_name

        norm_name = normalize_team_name(raw_team_name)
        curr_idx = len(team_entries)
        team_entries.append({
            "idx": idx,
            "loc": loc,
            "raw_team_obj": raw_team_obj,
            "team_obj": team_obj,
            "raw_team_name": raw_team_name,
            "raw_team_id": raw_team_id,
            "norm_name": norm_name,
        })
        norm_to_indices.setdefault(norm_name, []).append(curr_idx)

    # Pass 2: ID assignment & duplicate detection for JSON
    for norm_name, indices in norm_to_indices.items():
        if len(indices) > 1:
            anon_counter = 0
            for i in indices:
                entry = team_entries[i]
                entry["duplicate_name_detected"] = True
                if entry["raw_team_id"]:
                    entry["team_id"] = entry["raw_team_id"]
                    entry["is_temporary_id"] = False
                    entry["is_unresolved"] = False
                else:
                    anon_counter += 1
                    entry["team_id"] = generate_temporary_team_id(entry["raw_team_name"], anon_counter)
                    entry["is_temporary_id"] = True
                    entry["is_unresolved"] = True
                entry["team_obj"]["team_id"] = entry["team_id"]
                entry["team_obj"]["is_temporary_id"] = entry["is_temporary_id"]
                entry["team_obj"]["is_unresolved"] = entry["is_unresolved"]
                entry["team_obj"]["duplicate_name_detected"] = entry["duplicate_name_detected"]
        else:
            i = indices[0]
            entry = team_entries[i]
            entry["duplicate_name_detected"] = False
            if entry["raw_team_id"]:
                entry["team_id"] = entry["raw_team_id"]
                entry["is_temporary_id"] = False
                entry["is_unresolved"] = False
            else:
                entry["team_id"] = generate_stable_team_id(entry["raw_team_name"])
                entry["is_temporary_id"] = False
                entry["is_unresolved"] = False
            entry["team_obj"]["team_id"] = entry["team_id"]
            entry["team_obj"]["is_temporary_id"] = entry["is_temporary_id"]
            entry["team_obj"]["is_unresolved"] = entry["is_unresolved"]
            entry["team_obj"]["duplicate_name_detected"] = entry["duplicate_name_detected"]

    # Pass 3: Duplicate team name warnings for JSON
    for norm_name, indices in norm_to_indices.items():
        if len(indices) > 1:
            all_locs = [team_entries[i]["loc"] for i in indices]
            all_locs_str = ", ".join(all_locs)
            all_ids = [team_entries[i]["team_id"] for i in indices]

            for i in indices:
                entry = team_entries[i]
                other_ids = [tid for tid in all_ids if tid != entry["team_id"]]
                other_ids_str = ", ".join(other_ids) if other_ids else "none"

                if entry["is_temporary_id"]:
                    msg = (
                        f"Duplicate team name '{entry['raw_team_name']}' detected across multiple registrations "
                        f"({all_locs_str}). Assigned temporary unresolved ID '{entry['team_id']}' for {entry['loc']}. "
                        f"Conflicting team ID(s): {other_ids_str}."
                    )
                else:
                    msg = (
                        f"Duplicate team name '{entry['raw_team_name']}' detected across multiple registrations "
                        f"({all_locs_str}). Preserved explicit ID '{entry['team_id']}' for {entry['loc']}. "
                        f"Conflicting team ID(s): {other_ids_str}."
                    )

                warnings.append(
                    ValidationWarning(
                        team_id=entry["team_id"],
                        member_id="",
                        field="team_name",
                        message=msg,
                    )
                )

    # Pass 4: Process members and construct teams
    for entry in team_entries:
        team_obj = entry["team_obj"]
        loc = entry["loc"]

        # Track unmapped team keys
        for k in team_obj.keys():
            if k not in {
                "team_id",
                "team_name",
                "members",
                "custom_fields",
                "raw_data",
                "is_temporary_id",
                "is_unresolved",
                "duplicate_name_detected",
            }:
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

            raw_m_id = str(m_obj.get("member_id", "")).strip() if "member_id" in m_obj and m_obj["member_id"] is not None else ""
            if not raw_m_id:
                m_obj["member_id"] = generate_stable_member_id(team_obj["team_id"], m_idx + 1)

            # Track unmapped member keys
            for k in m_obj.keys():
                if k not in _RECOGNIZED_MEMBER_COLUMNS and k not in {"custom_fields", "raw_data", "field_statuses"}:
                    discovered_unmapped.add(k)

            # Build field_statuses
            field_statuses = {}
            if "member_id" in raw_m:
                field_statuses["member_id"] = (
                    FieldPresenceStatus.PRESENT if raw_m_id else FieldPresenceStatus.COLLECTED_BLANK
                )
            else:
                field_statuses["member_id"] = FieldPresenceStatus.NOT_COLLECTED

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

            if resume_index:
                matched_resume = _match_member_resume(m_obj, resume_index)
                if matched_resume:
                    fname, ftext = matched_resume
                    m_obj.setdefault("custom_fields", {})
                    m_obj["custom_fields"]["resume_text"] = ftext
                    m_obj["custom_fields"]["resume_filename"] = fname
                    m_obj["field_statuses"]["resume_url"] = FieldPresenceStatus.PRESENT
                    if not m_obj.get("resume_url"):
                        m_obj["resume_url"] = f"zip://{fname}"
                    matched_filenames.add(fname.lower())
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

    disambig_warnings = _disambiguate_cross_team_member_ids(teams, warnings)
    warnings.extend(disambig_warnings)
    if resume_index:
        total_unique_resumes = len({fn.lower() for fn, _ in resume_index.values()})
        unmatched_count = total_unique_resumes - len(matched_filenames)
        if unmatched_count > 0:
            warnings.append(
                ValidationWarning(
                    team_id="",
                    member_id="",
                    field="resumes_archive",
                    message=f"Companion resumes ZIP contained {total_unique_resumes} resume(s); {len(matched_filenames)} matched candidates, and {unmatched_count} were unmatched.",
                )
            )
        else:
            warnings.append(
                ValidationWarning(
                    team_id="",
                    member_id="",
                    field="resumes_archive",
                    message=f"All {total_unique_resumes} resume(s) in companion ZIP successfully matched candidates.",
                )
            )

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
    team_metas: dict[str, Any],
) -> tuple[list[TeamSchema], list[ValidationError], list[ValidationWarning]]:
    """Validate grouped rows into TeamSchema objects."""
    teams: list[TeamSchema] = []
    errors: list[ValidationError] = []
    warnings: list[ValidationWarning] = []

    for team_id, members_data in team_rows.items():
        meta = team_metas.get(team_id)
        if isinstance(meta, _TeamMeta):
            team_name = meta.team_name
            is_temporary_id = meta.is_temporary_id
            is_unresolved = meta.is_unresolved
            duplicate_name_detected = meta.duplicate_name_detected
            custom_fields = meta.custom_fields
            raw_data = meta.raw_data
        elif isinstance(meta, str):
            team_name = meta
            is_temporary_id = False
            is_unresolved = False
            duplicate_name_detected = False
            custom_fields = {}
            raw_data = {}
        else:
            team_name = team_id
            is_temporary_id = False
            is_unresolved = False
            duplicate_name_detected = False
            custom_fields = {}
            raw_data = {}

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

        team = TeamSchema(
            team_id=team_id,
            team_name=team_name,
            members=valid_members,
            is_temporary_id=is_temporary_id,
            is_unresolved=is_unresolved,
            duplicate_name_detected=duplicate_name_detected,
            custom_fields=custom_fields,
            raw_data=raw_data,
        )

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


def _disambiguate_cross_team_member_ids(
    teams: list[TeamSchema],
    existing_warnings: Optional[list[ValidationWarning]] = None,
) -> list[ValidationWarning]:
    """Detect any explicit member_id that appears in more than one team and disambiguate it.

    For colliding IDs only:
    - rewrites member.member_id to f"{team.team_id}_{member.member_id}"
    - preserves original in member.raw_data["original_member_id"] = original_id
    - creates a ValidationWarning
    - updates any prior warnings referencing old_id to new_id
    Non-colliding IDs are never modified.
    """
    member_to_teams: dict[str, set[str]] = {}
    for team in teams:
        for member in team.members:
            member_to_teams.setdefault(member.member_id, set()).add(team.team_id)

    colliding_ids = {m_id for m_id, t_ids in member_to_teams.items() if len(t_ids) > 1}
    if not colliding_ids:
        return []

    disambig_warnings: list[ValidationWarning] = []

    for team in teams:
        for member in team.members:
            if member.member_id in colliding_ids:
                old_id = member.member_id
                new_id = f"{team.team_id}_{old_id}"
                member.raw_data["original_member_id"] = old_id
                member.member_id = new_id

                if existing_warnings:
                    for w in existing_warnings:
                        if w.team_id == team.team_id and w.member_id == old_id:
                            w.member_id = new_id

                disambig_warnings.append(
                    ValidationWarning(
                        team_id=team.team_id,
                        member_id=new_id,
                        field="member_id",
                        message=f"Disambiguated colliding member_id '{old_id}' -> '{new_id}' across teams.",
                    )
                )

    return disambig_warnings

