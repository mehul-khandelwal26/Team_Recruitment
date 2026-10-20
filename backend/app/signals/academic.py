"""Academic signal analyzer for validating registration academic records.

Extracts and validates:
- CGPA or CPI metrics
- Academic year / graduation batch
- Scale-checked normalized CGPA

Supports organizer-provided column mappings, dynamic forms, and custom grading scales
without assuming CPI and CGPA share the same scale, without external API calls,
and without turning missing values into zero.
"""

from __future__ import annotations

import datetime
import re
from typing import Any, Optional

from app.schemas.ingestion import MemberSchema
from app.signals.base import BaseSignalExtractor
from app.signals.schemas import (
    ExtractedSignal,
    ExtractorDescriptor,
    SignalDefinition,
    SignalEvidence,
    SignalStatus,
)

# Standard known degree durations (years)
STANDARD_DEGREE_DURATIONS: dict[str, int] = {
    # 3-year undergraduate degrees
    "bca": 3,
    "b.sc": 3,
    "bsc": 3,
    "bba": 3,
    "b.com": 3,
    "bcom": 3,
    "ba": 3,
    "b.a": 3,
    "llb": 3,
    # 4-year undergraduate degrees
    "btech": 4,
    "b.tech": 4,
    "be": 4,
    "b.e": 4,
    "bs": 4,
    "b.s": 4,
    "b.des": 4,
    "bdes": 4,
    "b.pharm": 4,
    "bpharm": 4,
    # 5-year undergraduate / integrated degrees
    "dual degree": 5,
    "dual_degree": 5,
    "integrated m.tech": 5,
    "integrated mtech": 5,
    "integrated m.sc": 5,
    "integrated msc": 5,
    "b.arch": 5,
    "barch": 5,
    "mbbs": 5,
    "ba llb": 5,
    "bba llb": 5,
    # 2-year postgraduate degrees
    "mtech": 2,
    "m.tech": 2,
    "me": 2,
    "m.e": 2,
    "mba": 2,
    "mca": 2,
    "ms": 2,
    "m.s": 2,
    "m.sc": 2,
    "msc": 2,
    "ma": 2,
    "m.a": 2,
    "m.des": 2,
    "mdes": 2,
}

_FINAL_YEAR_REGEX = re.compile(r"^(?:final|senior)(?:\s+year)?$", re.IGNORECASE)
_PRE_FINAL_YEAR_REGEX = re.compile(r"^(?:pre-?final|pre\s+final)(?:\s+year)?$", re.IGNORECASE)

_NUMERIC_YEAR_PATTERNS: list[tuple[re.Pattern, int]] = [
    (re.compile(r"^(?:1|1st|first|freshman)(?:\s+year)?$", re.IGNORECASE), 1),
    (re.compile(r"^(?:2|2nd|second|sophomore)(?:\s+year)?$", re.IGNORECASE), 2),
    (re.compile(r"^(?:3|3rd|third|junior)(?:\s+year)?$", re.IGNORECASE), 3),
    (re.compile(r"^(?:4|4th|fourth)(?:\s+year)?$", re.IGNORECASE), 4),
    (re.compile(r"^(?:5|5th|fifth)(?:\s+year)?$", re.IGNORECASE), 5),
]

_GRAD_PATTERNS: list[re.Pattern] = [
    re.compile(r"^(?:graduate|postgraduate|pg|master|masters|m\.?tech|m\.?s|phd|mba)$", re.IGNORECASE),
]

_BATCH_YEAR_REGEX = re.compile(r"^(?:batch\s+(?:of\s+)?|class\s+of\s+)?(20\d{2})$", re.IGNORECASE)


def _ordinal(n: int) -> str:
    """Format positive integer as ordinal string (1st, 2nd, 3rd, 4th, 5th)."""
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def infer_degree_duration(degree_name: str) -> Optional[int]:
    """Infer degree duration in years from known degree identifiers."""
    cleaned = re.sub(r"[^a-zA-Z0-9\.]+", " ", str(degree_name).lower()).strip()
    if cleaned in STANDARD_DEGREE_DURATIONS:
        return STANDARD_DEGREE_DURATIONS[cleaned]
    # Check word boundaries within the string
    for deg_key, dur in STANDARD_DEGREE_DURATIONS.items():
        pattern = r"\b" + re.escape(deg_key) + r"\b"
        if re.search(pattern, cleaned):
            return dur
    return None


def resolve_degree_info(
    member: MemberSchema,
    config: Optional[dict[str, Any]] = None,
) -> tuple[Optional[str], Optional[int]]:
    """Determine degree name and duration in years from member records and config.

    Precedence:
    1. Explicit duration in config (`config['degree_duration']`).
    2. Explicit duration in member custom_fields or raw_data (`degree_duration`, `duration`).
    3. Duration inferred from degree name (from config or member records) via STANDARD_DEGREE_DURATIONS.
    """
    cfg = config or {}

    # 1. Explicit duration in config overrides all
    if "degree_duration" in cfg and cfg["degree_duration"] is not None:
        try:
            dur = int(cfg["degree_duration"])
            deg = cfg.get("degree") or _find_degree_name(member)
            return deg, dur
        except (ValueError, TypeError):
            pass

    # Degree name from config or member data
    degree_name = cfg.get("degree") or _find_degree_name(member)

    # 2. Explicit duration in member data
    duration_val = (
        member.custom_fields.get("degree_duration")
        or member.custom_fields.get("duration")
        or member.custom_fields.get("duration_years")
        or member.raw_data.get("degree_duration")
        or member.raw_data.get("duration")
    )
    if duration_val is not None:
        try:
            return degree_name, int(str(duration_val).strip())
        except (ValueError, TypeError):
            pass

    # 3. Inferred duration from degree_name
    if degree_name:
        dur = infer_degree_duration(degree_name)
        return degree_name, dur

    return degree_name, None


def _find_degree_name(member: MemberSchema) -> Optional[str]:
    """Look up degree name in candidate custom fields or raw data, falling back to resume education."""
    for key in ("degree", "degree_name", "program", "course", "branch", "qualification"):
        val = member.custom_fields.get(key) or member.raw_data.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()

    # Fallback to resume education if available
    edu = member.custom_fields.get("resume_education")
    if isinstance(edu, dict):
        deg = edu.get("degree_short") or edu.get("degree")
        if deg and str(deg).strip():
            return str(deg).strip()

    return None


def parse_academic_score(
    raw_val: Any,
    configured_scale: Optional[float] = None,
) -> tuple[Optional[float], Optional[float], Optional[str], Optional[str]]:
    """Parse a CGPA, CPI, or GPA string.

    Returns:
        (numeric_score, detected_scale, detected_system, error_message)
    """
    if raw_val is None:
        return None, None, None, None

    text = str(raw_val).strip()
    if not text:
        return None, None, None, None

    # Detect system tag if labeled
    detected_system = "cgpa"
    lower_text = text.lower()
    if "cpi" in lower_text:
        detected_system = "cpi"
    elif "gpa" in lower_text:
        detected_system = "gpa"
    elif "%" in text or "percent" in lower_text:
        detected_system = "percentage"

    # Remove labels
    cleaned = re.sub(r"(?i)\b(cgpa|cpi|gpa|score|grade|grade\s*point\s*average)\b", "", text)
    cleaned = cleaned.replace(":", " ").strip()

    # Check for explicit scale in string e.g. "8.5/10" or "3.8/4.0"
    explicit_scale: Optional[float] = None
    if "/" in cleaned:
        parts = cleaned.split("/", 1)
        score_part = parts[0].strip()
        scale_part = parts[1].strip()
        try:
            numeric_score = float(score_part)
            explicit_scale = float(scale_part)
        except ValueError:
            return None, None, None, f"Unable to parse score and scale from '{text}'."
    elif "%" in cleaned:
        score_part = cleaned.replace("%", "").strip()
        try:
            numeric_score = float(score_part)
            explicit_scale = 100.0
        except ValueError:
            return None, None, None, f"Unable to parse percentage from '{text}'."
    else:
        try:
            numeric_score = float(cleaned)
        except ValueError:
            return None, None, None, f"Unable to parse numeric CGPA/CPI from '{text}'."

    # Determine final scale
    final_scale = configured_scale or explicit_scale
    if final_scale is None:
        if detected_system == "percentage":
            final_scale = 100.0
        elif numeric_score <= 4.0 and detected_system in ("gpa",):
            final_scale = 4.0
        else:
            final_scale = 10.0

    # Validate range
    if numeric_score < 0.0:
        return None, None, None, f"Academic score cannot be negative: '{text}'."

    if numeric_score > final_scale:
        return None, None, None, f"Academic score {numeric_score} exceeds maximum scale {final_scale}."

    return numeric_score, final_scale, detected_system, None


def parse_academic_year(
    raw_val: Any,
    degree_duration: Optional[int] = None,
    degree_name: Optional[str] = None,
) -> tuple[Optional[str], Optional[int], Optional[str], dict[str, Any]]:
    """Parse and normalize academic year of study or batch.

    Returns:
        (normalized_label, year_number, error_message, metadata)
    """
    if raw_val is None:
        return None, None, None, {}

    text = str(raw_val).strip()
    if not text:
        return None, None, None, {}

    # 1. Relative "Final Year" / "Senior"
    if _FINAL_YEAR_REGEX.match(text):
        if degree_duration is not None:
            norm_label = f"{_ordinal(degree_duration)} Year"
            return norm_label, degree_duration, None, {
                "resolved_from": text,
                "degree_duration": degree_duration,
                "degree": degree_name,
                "is_resolved": True,
            }
        else:
            return "Final Year", None, None, {
                "resolved_from": text,
                "degree_duration": None,
                "degree": degree_name,
                "is_resolved": False,
                "note": "Degree duration unknown; preserved textual 'Final Year' without assuming degree duration.",
            }

    # 2. Relative "Pre-final Year" / "Prefinal"
    if _PRE_FINAL_YEAR_REGEX.match(text):
        if degree_duration is not None:
            pre_num = max(1, degree_duration - 1)
            norm_label = f"{_ordinal(pre_num)} Year"
            return norm_label, pre_num, None, {
                "resolved_from": text,
                "degree_duration": degree_duration,
                "degree": degree_name,
                "is_resolved": True,
            }
        else:
            return "Pre-final Year", None, None, {
                "resolved_from": text,
                "degree_duration": None,
                "degree": degree_name,
                "is_resolved": False,
                "note": "Degree duration unknown; preserved textual 'Pre-final Year' without assuming degree duration.",
            }

    # 3. Explicit numeric years (1st - 5th)
    for pattern, yr_num in _NUMERIC_YEAR_PATTERNS:
        if pattern.match(text):
            if degree_duration is not None and yr_num > degree_duration:
                return (
                    None,
                    None,
                    (
                        f"Conflicting academic data: Reported year of study ({yr_num}) "
                        f"exceeds duration for degree '{degree_name or 'unspecified'}' ({degree_duration} years)."
                    ),
                    {
                        "conflict": True,
                        "reported_year": yr_num,
                        "degree_duration": degree_duration,
                        "degree": degree_name,
                    },
                )
            return (
                f"{_ordinal(yr_num)} Year",
                yr_num,
                None,
                {
                    "year_number": yr_num,
                    "degree": degree_name,
                    "degree_duration": degree_duration,
                },
            )

    # 4. Graduation / batch year (e.g. 2026, Batch 2027, Class of 2025)
    batch_match = _BATCH_YEAR_REGEX.match(text)
    if batch_match:
        year_str = batch_match.group(1)
        grad_year = int(year_str)
        return (
            f"Batch {year_str}",
            None,
            None,
            {
                "graduation_year": grad_year,
                "is_graduation_batch": True,
                "degree": degree_name,
                "degree_duration": degree_duration,
            },
        )

    # 5. Postgraduate patterns
    for pattern in _GRAD_PATTERNS:
        if pattern.match(text):
            return (
                "Postgraduate",
                None,
                None,
                {"level": "postgraduate", "degree": degree_name},
            )

    return None, None, f"Unrecognized academic year format: '{text}'.", {}


class AcademicMetricsAnalyzer(BaseSignalExtractor):
    """Analyzer for evaluating and normalizing candidate academic information."""

    @property
    def descriptor(self) -> ExtractorDescriptor:
        return ExtractorDescriptor(
            extractor_id="academic_metrics",
            name="Academic Metrics Processor",
            description="Normalizes CGPA, CPI, and academic standings across diverse grading scales.",
            category="academic",
            required_inputs=["cgpa"],
            optional_inputs=["academic_year"],
            produced_signals=[
                "academic_cgpa",
                "academic_year",
                "normalized_cgpa_10_scale",
            ],
            signals=[
                SignalDefinition(
                    signal_key="academic_cgpa",
                    name="Academic Score (CGPA / CPI)",
                    description="Validated academic score (CGPA, CPI, or GPA) on its recorded scale.",
                    category="academic",
                    value_type="float",
                    unit="points",
                ),
                SignalDefinition(
                    signal_key="academic_year",
                    name="Academic Year / Batch",
                    description="Normalized academic year of study (e.g. '3rd Year') or graduation batch.",
                    category="academic",
                    value_type="string",
                ),
                SignalDefinition(
                    signal_key="normalized_cgpa_10_scale",
                    name="Normalized CGPA (10-Point Scale)",
                    description="CGPA normalized to standard 10-point scale with explicit conversion rules.",
                    category="academic",
                    value_type="float",
                    unit="points",
                ),
            ],
            is_enabled_by_default=False,
            optional_config={
                "cgpa_scale": "Explicit maximum scale (e.g. 10.0, 4.0, 100.0)",
                "cgpa_field": "Custom source column name for CGPA/CPI in registration data",
                "academic_year_field": "Custom source column name for Academic Year in registration data",
                "allow_scale_conversion": "Explicit boolean flag allowing conversion between scales",
                "degree": "Target degree name (e.g. 'B.Tech', 'BCA', 'MCA', 'Dual Degree')",
                "degree_duration": "Explicit degree duration in years (e.g. 3, 4, 5, 2)",
            },
        )

    def extract(
        self,
        member: MemberSchema,
        selected_signals: Optional[set[str]] = None,
        config: Optional[dict[str, Any]] = None,
    ) -> list[ExtractedSignal]:
        """Extract and validate academic signals for a team member."""
        target_signals = selected_signals or set(self.descriptor.produced_signals)
        cfg = config or {}
        results: list[ExtractedSignal] = []
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Resolve degree info (degree_name, degree_duration)
        degree_name, degree_duration = resolve_degree_info(member, cfg)

        # Resolve raw CGPA / CPI value and source field name
        cgpa_val, cgpa_field_name = self._resolve_cgpa_value(member, cfg)
        cgpa_source = "registration_data"

        # Resolve raw Academic Year value and source field name
        year_val, year_field_name = self._resolve_year_value(member, cfg)
        year_source = "registration_data"

        # Fallback to resume parser if academic metrics are missing from registration CSV
        from app.signals.resume import get_or_extract_resume_signals

        resume_data: Optional[dict[str, Any]] = None
        if (
            (cgpa_val is None or (isinstance(cgpa_val, str) and not cgpa_val.strip()))
            or (year_val is None or (isinstance(year_val, str) and not year_val.strip()))
            or not degree_name
        ):
            resume_data = get_or_extract_resume_signals(member, cfg)

        if resume_data:
            edu_info = resume_data.get("resume_education") or {}

            # Resume fallback for CGPA / CPI
            if (cgpa_val is None or (isinstance(cgpa_val, str) and not cgpa_val.strip())) and edu_info.get("gpa"):
                cgpa_val = edu_info["gpa"]
                cgpa_field_name = "resume_education.gpa"
                cgpa_source = "resume_parser"

            # Resume fallback for Academic Year
            if year_val is None or (isinstance(year_val, str) and not year_val.strip()):
                if edu_info.get("graduation_year"):
                    year_val = str(edu_info["graduation_year"])
                    year_field_name = "resume_education.graduation_year"
                    year_source = "resume_parser"
                else:
                    # Check plain resume text for explicit year patterns
                    r_text = resume_data.get("resume_text", "")
                    if r_text:
                        for pat, yr_num in _NUMERIC_YEAR_PATTERNS:
                            if pat.search(r_text):
                                year_val = f"{_ordinal(yr_num)} year"
                                year_field_name = "resume_text.year"
                                year_source = "resume_parser"
                                break
                        if not year_val:
                            if _FINAL_YEAR_REGEX.search(r_text):
                                year_val = "Final Year"
                                year_field_name = "resume_text.year"
                                year_source = "resume_parser"
                            elif _PRE_FINAL_YEAR_REGEX.search(r_text):
                                year_val = "Pre-Final Year"
                                year_field_name = "resume_text.year"
                                year_source = "resume_parser"

            # Resume fallback for Degree info
            if not degree_name and (edu_info.get("degree_short") or edu_info.get("degree")):
                degree_name = edu_info.get("degree_short") or edu_info.get("degree")
                if not degree_duration:
                    degree_duration = infer_degree_duration(degree_name)

        # Parse CGPA
        configured_scale = None
        if "cgpa_scale" in cfg and cfg["cgpa_scale"] is not None:
            try:
                configured_scale = float(cfg["cgpa_scale"])
            except (ValueError, TypeError):
                configured_scale = None

        score, scale, system, score_err = parse_academic_score(cgpa_val, configured_scale=configured_scale)

        # -------------------------------------------------------------------
        # Signal: academic_cgpa
        # -------------------------------------------------------------------
        if "academic_cgpa" in target_signals:
            if cgpa_val is None or (isinstance(cgpa_val, str) and not cgpa_val.strip()):
                results.append(
                    ExtractedSignal(
                        signal_key="academic_cgpa",
                        category="academic",
                        value=None,
                        status=SignalStatus.NOT_APPLICABLE,
                        error_message="Academic score (CGPA/CPI) was not provided in CSV or candidate resume.",
                        evidence=SignalEvidence(
                            source="registration_data",
                            raw_input=None,
                            metadata={"reason": "missing_input", "source_field": cgpa_field_name},
                        ),
                    )
                )
            elif score_err or score is None:
                results.append(
                    ExtractedSignal(
                        signal_key="academic_cgpa",
                        category="academic",
                        value=None,
                        status=SignalStatus.FAILED,
                        error_message=score_err or "Invalid academic score.",
                        evidence=SignalEvidence(
                            source=cgpa_source,
                            raw_input=str(cgpa_val),
                            metadata={"source_field": cgpa_field_name, "error": score_err},
                        ),
                    )
                )
            else:
                cgpa_conf = 1.0 if cgpa_source == "registration_data" else 0.85
                results.append(
                    ExtractedSignal(
                        signal_key="academic_cgpa",
                        category="academic",
                        value=score,
                        status=SignalStatus.EXTRACTED,
                        evidence=SignalEvidence(
                            source=cgpa_source,
                            raw_input=str(cgpa_val),
                            extracted_at=timestamp,
                            confidence=cgpa_conf,
                            metadata={
                                "raw_value": str(cgpa_val),
                                "numeric_score": score,
                                "scale": scale,
                                "system": system,
                                "source_field": cgpa_field_name,
                                **({"inferred_from_resume": True} if cgpa_source == "resume_parser" else {}),
                            },
                        ),
                    )
                )

        # -------------------------------------------------------------------
        # Signal: normalized_cgpa_10_scale
        # -------------------------------------------------------------------
        if "normalized_cgpa_10_scale" in target_signals:
            if cgpa_val is None or (isinstance(cgpa_val, str) and not cgpa_val.strip()):
                results.append(
                    ExtractedSignal(
                        signal_key="normalized_cgpa_10_scale",
                        category="academic",
                        value=None,
                        status=SignalStatus.NOT_APPLICABLE,
                        error_message="Academic score was not provided.",
                        evidence=SignalEvidence(
                            source="registration_data",
                            raw_input=None,
                            metadata={"reason": "missing_input", "source_field": cgpa_field_name},
                        ),
                    )
                )
            elif score_err or score is None or scale is None:
                results.append(
                    ExtractedSignal(
                        signal_key="normalized_cgpa_10_scale",
                        category="academic",
                        value=None,
                        status=SignalStatus.FAILED,
                        error_message=score_err or "Invalid academic score.",
                        evidence=SignalEvidence(
                            source=cgpa_source,
                            raw_input=str(cgpa_val),
                            metadata={"source_field": cgpa_field_name, "error": score_err},
                        ),
                    )
                )
            elif scale == 10.0:
                norm_conf = 1.0 if cgpa_source == "registration_data" else 0.85
                results.append(
                    ExtractedSignal(
                        signal_key="normalized_cgpa_10_scale",
                        category="academic",
                        value=score,
                        status=SignalStatus.EXTRACTED,
                        evidence=SignalEvidence(
                            source=cgpa_source,
                            raw_input=str(cgpa_val),
                            extracted_at=timestamp,
                            confidence=norm_conf,
                            metadata={
                                "raw_value": str(cgpa_val),
                                "normalized_score": score,
                                "original_scale": 10.0,
                                "target_scale": 10.0,
                                "source_field": cgpa_field_name,
                                **({"inferred_from_resume": True} if cgpa_source == "resume_parser" else {}),
                            },
                        ),
                    )
                )
            else:
                # Scale differs from 10.0 (e.g. 4.0 or 100.0)
                allow_conv = bool(cfg.get("allow_scale_conversion", False))
                if not allow_conv:
                    results.append(
                        ExtractedSignal(
                            signal_key="normalized_cgpa_10_scale",
                            category="academic",
                            value=None,
                            status=SignalStatus.FAILED,
                            error_message=(
                                f"Score is on a {scale}-point scale. Conversion to 10-point scale "
                                "requires explicit configuration ('allow_scale_conversion': True)."
                            ),
                            evidence=SignalEvidence(
                                source=cgpa_source,
                                raw_input=str(cgpa_val),
                                metadata={
                                    "original_scale": scale,
                                    "conversion_allowed": False,
                                    "source_field": cgpa_field_name,
                                },
                            ),
                        )
                    )
                else:
                    normalized_score = round((score / scale) * 10.0, 2)
                    norm_conv_conf = 0.9 if cgpa_source == "registration_data" else 0.80
                    results.append(
                        ExtractedSignal(
                            signal_key="normalized_cgpa_10_scale",
                            category="academic",
                            value=normalized_score,
                            status=SignalStatus.EXTRACTED,
                            evidence=SignalEvidence(
                                source=cgpa_source,
                                raw_input=str(cgpa_val),
                                extracted_at=timestamp,
                                confidence=norm_conv_conf,
                                metadata={
                                    "raw_value": str(cgpa_val),
                                    "original_score": score,
                                    "original_scale": scale,
                                    "normalized_score": normalized_score,
                                    "target_scale": 10.0,
                                    "source_field": cgpa_field_name,
                                    **({"inferred_from_resume": True} if cgpa_source == "resume_parser" else {}),
                                },
                            ),
                        )
                    )

        # -------------------------------------------------------------------
        # Signal: academic_year
        # -------------------------------------------------------------------
        if "academic_year" in target_signals:
            if year_val is None or (isinstance(year_val, str) and not year_val.strip()):
                results.append(
                    ExtractedSignal(
                        signal_key="academic_year",
                        category="academic",
                        value=None,
                        status=SignalStatus.NOT_APPLICABLE,
                        error_message="Academic year was not provided in CSV or candidate resume.",
                        evidence=SignalEvidence(
                            source="registration_data",
                            raw_input=None,
                            metadata={"reason": "missing_input", "source_field": year_field_name},
                        ),
                    )
                )
            else:
                norm_label, yr_num, yr_err, yr_meta = parse_academic_year(
                    year_val, degree_duration=degree_duration, degree_name=degree_name
                )
                if yr_err or norm_label is None:
                    results.append(
                        ExtractedSignal(
                            signal_key="academic_year",
                            category="academic",
                            value=None,
                            status=SignalStatus.FAILED,
                            error_message=yr_err or "Invalid academic year format.",
                            evidence=SignalEvidence(
                                source=year_source,
                                raw_input=str(year_val),
                                metadata={
                                    "source_field": year_field_name,
                                    "error": yr_err,
                                    **yr_meta,
                                },
                            ),
                        )
                    )
                else:
                    ev_metadata = {
                        "raw_value": str(year_val),
                        "normalized_year": norm_label,
                        "year_number": yr_num,
                        "source_field": year_field_name,
                        **({"inferred_from_resume": True} if year_source == "resume_parser" else {}),
                        **yr_meta,
                    }
                    year_conf = 1.0 if year_source == "registration_data" else 0.85
                    results.append(
                        ExtractedSignal(
                            signal_key="academic_year",
                            category="academic",
                            value=norm_label,
                            status=SignalStatus.EXTRACTED,
                            evidence=SignalEvidence(
                                source=year_source,
                                raw_input=str(year_val),
                                extracted_at=timestamp,
                                confidence=year_conf,
                                metadata=ev_metadata,
                            ),
                        )
                    )

        return results

    def _resolve_cgpa_value(self, member: MemberSchema, config: dict[str, Any]) -> tuple[Any, str]:
        """Resolve CGPA value from canonical field or mapped custom fields."""
        # Check custom field configured by organizer
        custom_field_name = config.get("cgpa_field")
        if custom_field_name:
            if custom_field_name in member.custom_fields:
                return member.custom_fields[custom_field_name], custom_field_name
            if custom_field_name in member.raw_data:
                return member.raw_data[custom_field_name], custom_field_name

        # Check canonical member.cgpa
        if member.cgpa is not None:
            return member.cgpa, "cgpa"

        # Check common aliases in custom_fields
        for alias in ("cpi", "gpa", "grade_point_average", "academic_score", "grades"):
            if alias in member.custom_fields and member.custom_fields[alias] is not None:
                return member.custom_fields[alias], alias

        return None, "cgpa"

    def _resolve_year_value(self, member: MemberSchema, config: dict[str, Any]) -> tuple[Any, str]:
        """Resolve academic year value from canonical field or mapped custom fields."""
        # Check custom field configured by organizer
        custom_field_name = config.get("academic_year_field")
        if custom_field_name:
            if custom_field_name in member.custom_fields:
                return member.custom_fields[custom_field_name], custom_field_name
            if custom_field_name in member.raw_data:
                return member.raw_data[custom_field_name], custom_field_name

        # Check canonical member.academic_year
        if member.academic_year is not None:
            return member.academic_year, "academic_year"

        # Check common aliases in custom_fields
        for alias in ("year", "year_of_study", "batch", "graduation_year", "class"):
            if alias in member.custom_fields and member.custom_fields[alias] is not None:
                return member.custom_fields[alias], alias

        return None, "academic_year"
