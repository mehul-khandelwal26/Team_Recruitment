"""Field discovery and schema inspection for registration files.

Analyzes raw CSV and JSON uploads to discover original column/field names,
infer data types, compute population statistics, detect canonical fields,
and provide safe, configurable mapping suggestions.
"""

from __future__ import annotations

import io
import json
import re
from typing import Any, Optional

import pandas as pd

from app.schemas.mapping import (
    CANONICAL_ALIASES,
    REQUIRED_STRUCTURAL_FIELDS,
    CanonicalField,
    CanonicalFieldInfo,
    DiscoveredField,
    FieldDiscoveryResponse,
)

# Canonical field information descriptions for frontend display
CANONICAL_FIELD_CATALOG: list[CanonicalFieldInfo] = [
    CanonicalFieldInfo(
        field_key=CanonicalField.TEAM_ID.value,
        display_name="Team ID",
        is_structural_required=True,
        description="Unique identifier for each team (e.g. 'T01', 'TEAM-42').",
        category="structural",
    ),
    CanonicalFieldInfo(
        field_key=CanonicalField.TEAM_NAME.value,
        display_name="Team Name",
        is_structural_required=True,
        description="Display name of the team.",
        category="structural",
    ),
    CanonicalFieldInfo(
        field_key=CanonicalField.MEMBER_ID.value,
        display_name="Member ID",
        is_structural_required=True,
        description="Unique identifier for each participant.",
        category="structural",
    ),
    CanonicalFieldInfo(
        field_key=CanonicalField.MEMBER_NAME.value,
        display_name="Member Name",
        is_structural_required=True,
        description="Full display name of the participant.",
        category="structural",
    ),
    CanonicalFieldInfo(
        field_key=CanonicalField.EMAIL.value,
        display_name="Email Address",
        is_structural_required=False,
        description="Participant's contact email address.",
        category="profile",
    ),
    CanonicalFieldInfo(
        field_key=CanonicalField.RESUME_URL.value,
        display_name="Resume / CV URL",
        is_structural_required=False,
        description="Link to participant's resume or curriculum vitae.",
        category="profile",
    ),
    CanonicalFieldInfo(
        field_key=CanonicalField.GITHUB_URL.value,
        display_name="GitHub Profile URL",
        is_structural_required=False,
        description="Link to participant's GitHub profile.",
        category="profile",
    ),
    CanonicalFieldInfo(
        field_key=CanonicalField.LINKEDIN_URL.value,
        display_name="LinkedIn Profile URL",
        is_structural_required=False,
        description="Link to participant's LinkedIn profile (optional).",
        category="profile",
    ),
    CanonicalFieldInfo(
        field_key=CanonicalField.PORTFOLIO_URL.value,
        display_name="Portfolio URL",
        is_structural_required=False,
        description="Link to candidate's personal portfolio or website.",
        category="profile",
    ),
    CanonicalFieldInfo(
        field_key=CanonicalField.CGPA.value,
        display_name="CGPA / GPA / CPI",
        is_structural_required=False,
        description="Academic score or grade point average.",
        category="academic",
    ),
    CanonicalFieldInfo(
        field_key=CanonicalField.ACADEMIC_YEAR.value,
        display_name="Academic Year / Batch",
        is_structural_required=False,
        description="Current year of study or expected graduation year.",
        category="academic",
    ),
]


def discover_fields_from_bytes(
    raw_bytes: bytes,
    file_name: str,
    file_type: str = "csv",
) -> FieldDiscoveryResponse:
    """Analyze file bytes and return a comprehensive field discovery response."""
    if file_type.lower() == "json" or file_name.lower().endswith(".json"):
        return _discover_json_fields(raw_bytes, file_name)
    return _discover_csv_fields(raw_bytes, file_name)


# ---------------------------------------------------------------------------
# CSV Discovery
# ---------------------------------------------------------------------------


def _discover_csv_fields(raw_bytes: bytes, file_name: str) -> FieldDiscoveryResponse:
    from app.ingestion.parser import decode_text_bytes, detect_csv_delimiter

    text = decode_text_bytes(raw_bytes)
    if not text:
        return FieldDiscoveryResponse(
            file_name=file_name,
            file_type="csv",
            total_records=0,
            discovered_fields=[],
            missing_structural_fields=list(REQUIRED_STRUCTURAL_FIELDS),
            suggested_mappings={},
            canonical_fields=CANONICAL_FIELD_CATALOG,
        )

    sep = detect_csv_delimiter(text)

    try:
        df = pd.read_csv(io.StringIO(text), sep=sep, dtype=str, keep_default_na=False)
    except Exception:
        return FieldDiscoveryResponse(
            file_name=file_name,
            file_type="csv",
            total_records=0,
            discovered_fields=[],
            missing_structural_fields=list(REQUIRED_STRUCTURAL_FIELDS),
            suggested_mappings={},
            canonical_fields=CANONICAL_FIELD_CATALOG,
        )

    total_rows = len(df)
    # Pass 1: Raw matching for all discovered columns
    raw_matches: list[dict[str, Any]] = []
    for col in df.columns:
        original_col_name = str(col)
        series = df[col].astype(str)
        values = [v.strip() for v in series if v.strip()]

        total_count = total_rows
        non_empty_count = len(values)
        missing_count = total_count - non_empty_count
        is_consistently_populated = (
            non_empty_count / total_count >= 0.8 if total_count > 0 else True
        )
        sample_values = list(dict.fromkeys(values[:5]))  # preserve order, unique
        inferred_type = _infer_type(values)
        match_info = _match_canonical(original_col_name)

        raw_matches.append({
            "col_name": original_col_name,
            "inferred_type": inferred_type,
            "sample_values": sample_values,
            "total_count": total_count,
            "non_empty_count": non_empty_count,
            "missing_count": missing_count,
            "is_consistently_populated": is_consistently_populated,
            "target": match_info["canonical_field"],
            "confidence": match_info["confidence"],
            "is_exact": match_info["is_exact"],
            "reason": match_info["reason"],
        })

    # Pass 2: Conflict resolution by canonical target (highest confidence wins)
    target_groups: dict[str, list[dict[str, Any]]] = {}
    for m in raw_matches:
        tgt = m["target"]
        if tgt:
            target_groups.setdefault(tgt, []).append(m)

    winning_cols: dict[str, str] = {}
    for tgt, candidates in target_groups.items():
        if len(candidates) == 1:
            winning_cols[tgt] = candidates[0]["col_name"]
        else:
            sorted_cands = sorted(
                candidates,
                key=lambda c: (1 if c["is_exact"] else 0, c["confidence"]),
                reverse=True,
            )
            winning_cols[tgt] = sorted_cands[0]["col_name"]

    # Build final discovered_fields and suggested_mappings
    discovered_fields: list[DiscoveredField] = []
    suggested_mappings: dict[str, str] = {}
    matched_canonical_fields: set[str] = set()

    for m in raw_matches:
        col_name = m["col_name"]
        tgt = m["target"]

        if tgt and winning_cols.get(tgt) == col_name:
            is_recognized = m["is_exact"]
            status = "recognized" if is_recognized else "suggested"
            recognized_target = tgt if is_recognized else None
            suggested_target = tgt
            confidence = m["confidence"]
            reason = m["reason"]
            suggested_mappings[col_name] = tgt
            matched_canonical_fields.add(tgt)
        elif tgt:
            winner = winning_cols[tgt]
            status = "unmapped"
            is_recognized = False
            recognized_target = None
            suggested_target = None
            confidence = 0.0
            reason = f"Duplicate candidate for canonical '{tgt}'; assigned to higher-confidence column '{winner}'"
        else:
            status = "unmapped"
            is_recognized = False
            recognized_target = None
            suggested_target = None
            confidence = 0.0
            reason = m["reason"]

        is_structural = (
            tgt in REQUIRED_STRUCTURAL_FIELDS if tgt and suggested_target else False
        )

        discovered_fields.append(
            DiscoveredField(
                original_name=col_name,
                normalized_key=_normalize_key(col_name),
                inferred_type=m["inferred_type"],
                sample_values=m["sample_values"],
                total_count=m["total_count"],
                non_empty_count=m["non_empty_count"],
                missing_count=m["missing_count"],
                is_consistently_populated=m["is_consistently_populated"],
                is_recognized=is_recognized,
                recognized_field=recognized_target,
                suggested_mapping=suggested_target,
                suggestion_confidence=confidence,
                suggestion_reason=reason,
                is_structural_required=is_structural,
                status=status,
            )
        )

    # Detect teams if team_id or team_name column exists
    total_teams: Optional[int] = None
    for df_item in discovered_fields:
        if df_item.suggested_mapping == CanonicalField.TEAM_ID.value:
            total_teams = int(df[df_item.original_name].nunique())
            break
    if total_teams is None:
        for df_item in discovered_fields:
            if df_item.suggested_mapping == CanonicalField.TEAM_NAME.value:
                total_teams = int(df[df_item.original_name].nunique())
                break

    missing_structural = [
        f for f in sorted(REQUIRED_STRUCTURAL_FIELDS) if f not in matched_canonical_fields
    ]

    return FieldDiscoveryResponse(
        file_name=file_name,
        file_type="csv",
        total_records=total_rows,
        total_teams_detected=total_teams,
        total_members_detected=total_rows,
        discovered_fields=discovered_fields,
        missing_structural_fields=missing_structural,
        suggested_mappings=suggested_mappings,
        canonical_fields=CANONICAL_FIELD_CATALOG,
    )


# ---------------------------------------------------------------------------
# JSON Discovery
# ---------------------------------------------------------------------------


def _discover_json_fields(raw_bytes: bytes, file_name: str) -> FieldDiscoveryResponse:
    from app.ingestion.parser import decode_text_bytes

    text = decode_text_bytes(raw_bytes)
    if not text:
        return FieldDiscoveryResponse(
            file_name=file_name,
            file_type="json",
            total_records=0,
            discovered_fields=[],
            missing_structural_fields=list(REQUIRED_STRUCTURAL_FIELDS),
            suggested_mappings={},
            canonical_fields=CANONICAL_FIELD_CATALOG,
        )

    try:
        data = json.loads(text)
    except Exception:
        return FieldDiscoveryResponse(
            file_name=file_name,
            file_type="json",
            total_records=0,
            discovered_fields=[],
            missing_structural_fields=list(REQUIRED_STRUCTURAL_FIELDS),
            suggested_mappings={},
            canonical_fields=CANONICAL_FIELD_CATALOG,
        )

    if not isinstance(data, list):
        return FieldDiscoveryResponse(
            file_name=file_name,
            file_type="json",
            total_records=0,
            discovered_fields=[],
            missing_structural_fields=list(REQUIRED_STRUCTURAL_FIELDS),
            suggested_mappings={},
            canonical_fields=CANONICAL_FIELD_CATALOG,
        )

    # Collect team-level and member-level keys
    team_keys: dict[str, list[Any]] = {}
    member_keys: dict[str, list[Any]] = {}
    total_teams = len(data)
    total_members = 0

    for team_obj in data:
        if isinstance(team_obj, dict):
            for k, v in team_obj.items():
                if k != "members":
                    team_keys.setdefault(k, []).append(v)
            members = team_obj.get("members", [])
            if isinstance(members, list):
                total_members += len(members)
                for m in members:
                    if isinstance(m, dict):
                        for mk, mv in m.items():
                            member_keys.setdefault(mk, []).append(mv)

    # Combine keys, giving team-level precedence for team fields
    all_keys: dict[str, tuple[list[Any], int]] = {}
    for k, vals in team_keys.items():
        all_keys[k] = (vals, total_teams)
    for k, vals in member_keys.items():
        if k in all_keys:
            # Field exists at both levels; merge values
            all_keys[k] = (all_keys[k][0] + vals, max(total_teams, total_members))
        else:
            all_keys[k] = (vals, total_members)

    raw_matches_json: list[dict[str, Any]] = []
    for original_key, (vals, total_count) in all_keys.items():
        non_empty = [str(v).strip() for v in vals if v is not None and str(v).strip()]
        non_empty_count = len(non_empty)
        missing_count = total_count - non_empty_count
        is_consistently_populated = (
            non_empty_count / total_count >= 0.8 if total_count > 0 else True
        )
        sample_values = list(dict.fromkeys(non_empty[:5]))
        inferred_type = _infer_type(non_empty)

        match_info = _match_canonical(original_key)
        raw_matches_json.append({
            "key": original_key,
            "inferred_type": inferred_type,
            "sample_values": sample_values,
            "total_count": total_count,
            "non_empty_count": non_empty_count,
            "missing_count": missing_count,
            "is_consistently_populated": is_consistently_populated,
            "target": match_info["canonical_field"],
            "confidence": match_info["confidence"],
            "is_exact": match_info["is_exact"],
            "reason": match_info["reason"],
        })

    # Conflict resolution across canonical targets (highest confidence wins)
    target_groups_json: dict[str, list[dict[str, Any]]] = {}
    for m in raw_matches_json:
        tgt = m["target"]
        if tgt:
            target_groups_json.setdefault(tgt, []).append(m)

    winning_cols_json: dict[str, str] = {}
    for tgt, candidates in target_groups_json.items():
        if len(candidates) == 1:
            winning_cols_json[tgt] = candidates[0]["key"]
        else:
            sorted_cands = sorted(
                candidates,
                key=lambda c: (1 if c["is_exact"] else 0, c["confidence"]),
                reverse=True,
            )
            winning_cols_json[tgt] = sorted_cands[0]["key"]

    discovered_fields: list[DiscoveredField] = []
    suggested_mappings: dict[str, str] = {}
    matched_canonical_fields: set[str] = set()

    for m in raw_matches_json:
        original_key = m["key"]
        tgt = m["target"]

        if tgt and winning_cols_json.get(tgt) == original_key:
            is_recognized = m["is_exact"]
            status = "recognized" if is_recognized else "suggested"
            recognized_target = tgt if is_recognized else None
            suggested_target = tgt
            confidence = m["confidence"]
            reason = m["reason"]
            suggested_mappings[original_key] = tgt
            matched_canonical_fields.add(tgt)
        elif tgt:
            winner = winning_cols_json[tgt]
            status = "unmapped"
            is_recognized = False
            recognized_target = None
            suggested_target = None
            confidence = 0.0
            reason = f"Duplicate candidate for canonical '{tgt}'; assigned to higher-confidence field '{winner}'"
        else:
            status = "unmapped"
            is_recognized = False
            recognized_target = None
            suggested_target = None
            confidence = 0.0
            reason = m["reason"]

        is_structural = tgt in REQUIRED_STRUCTURAL_FIELDS if tgt and suggested_target else False

        discovered_fields.append(
            DiscoveredField(
                original_name=original_key,
                normalized_key=_normalize_key(original_key),
                inferred_type=m["inferred_type"],
                sample_values=m["sample_values"],
                total_count=m["total_count"],
                non_empty_count=m["non_empty_count"],
                missing_count=m["missing_count"],
                is_consistently_populated=m["is_consistently_populated"],
                is_recognized=is_recognized,
                recognized_field=recognized_target,
                suggested_mapping=suggested_target,
                suggestion_confidence=confidence,
                suggestion_reason=reason,
                is_structural_required=is_structural,
                status=status,
            )
        )

    missing_structural = [
        f for f in sorted(REQUIRED_STRUCTURAL_FIELDS) if f not in matched_canonical_fields
    ]

    return FieldDiscoveryResponse(
        file_name=file_name,
        file_type="json",
        total_records=total_members,
        total_teams_detected=total_teams,
        total_members_detected=total_members,
        discovered_fields=discovered_fields,
        missing_structural_fields=missing_structural,
        suggested_mappings=suggested_mappings,
        canonical_fields=CANONICAL_FIELD_CATALOG,
    )


# ---------------------------------------------------------------------------
# Matching & Inference Helpers
# ---------------------------------------------------------------------------


def _normalize_key(k: str) -> str:
    """Normalize a key string: lowercase, replace punctuation/spaces with single space."""
    cleaned = re.sub(r"[_\-\s]+", " ", k.strip().lower())
    return cleaned


def _match_canonical(original_name: str) -> dict[str, Any]:
    """Find the best canonical field match for a given column/property name."""
    norm = _normalize_key(original_name)
    raw_lower = original_name.strip().lower()

    # 1. Exact match with canonical enum values
    for canonical in CanonicalField:
        c_val = canonical.value
        if raw_lower == c_val or norm == c_val.replace("_", " "):
            return {
                "canonical_field": c_val,
                "confidence": 1.0,
                "is_exact": True,
                "reason": f"Exact match to recognized '{c_val}' field",
            }

    # 2. Match against known aliases
    for canonical_key, aliases in CANONICAL_ALIASES.items():
        for alias in aliases:
            norm_alias = _normalize_key(alias)
            if norm == norm_alias or raw_lower == alias.lower():
                # Specific caveat for CPI vs CGPA
                if norm == "cpi":
                    return {
                        "canonical_field": canonical_key,
                        "confidence": 0.75,
                        "is_exact": False,
                        "reason": "Matches related academic metric 'CPI' (note: scale may differ from standard 4.0/10.0 CGPA)",
                    }
                # Handles / user IDs get 0.70 confidence so full URLs/links take precedence
                if alias in ("github_id", "github id", "github_handle", "github handle"):
                    return {
                        "canonical_field": canonical_key,
                        "confidence": 0.70,
                        "is_exact": False,
                        "reason": f"Matches GitHub handle identifier alias '{alias}' for '{canonical_key}'",
                    }
                return {
                    "canonical_field": canonical_key,
                    "confidence": 0.90,
                    "is_exact": False,
                    "reason": f"Matches common alias '{alias}' for '{canonical_key}'",
                }

    # 3. Unmapped / Custom field
    return {
        "canonical_field": None,
        "confidence": 0.0,
        "is_exact": False,
        "reason": "Unrecognized custom field; will be preserved as custom data without scoring impact",
    }


def _infer_type(values: list[str]) -> str:
    """Infer high-level data type from sample non-empty values."""
    if not values:
        return "string"

    email_count = sum(1 for v in values if "@" in v and "." in v and " " not in v)
    if email_count / len(values) >= 0.7:
        return "email"

    url_count = sum(1 for v in values if v.startswith("http://") or v.startswith("https://"))
    if url_count / len(values) >= 0.7:
        return "url"

    num_count = 0
    for v in values:
        try:
            float(v)
            num_count += 1
        except ValueError:
            pass
    if num_count / len(values) >= 0.7:
        return "number"

    bool_count = sum(1 for v in values if v.lower() in {"true", "false", "yes", "no", "1", "0"})
    if bool_count / len(values) >= 0.7:
        return "boolean"

    avg_len = sum(len(v) for v in values) / len(values)
    if avg_len > 60:
        return "text"

    return "string"
