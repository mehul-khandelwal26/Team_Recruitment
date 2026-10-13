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

# Known academic year text patterns mapped to standard representations
_YEAR_PATTERNS: list[tuple[re.Pattern, str, int]] = [
    (re.compile(r"^(?:1|1st|first|freshman)(?:\s+year)?$", re.IGNORECASE), "1st Year", 1),
    (re.compile(r"^(?:2|2nd|second|sophomore)(?:\s+year)?$", re.IGNORECASE), "2nd Year", 2),
    (re.compile(r"^(?:3|3rd|third|junior)(?:\s+year)?$", re.IGNORECASE), "3rd Year", 3),
    (re.compile(r"^(?:4|4th|fourth|senior|final)(?:\s+year)?$", re.IGNORECASE), "4th Year", 4),
    (re.compile(r"^(?:5|5th|fifth)(?:\s+year)?$", re.IGNORECASE), "5th Year", 5),
]

_GRAD_PATTERNS: list[re.Pattern] = [
    re.compile(r"^(?:graduate|postgraduate|pg|master|masters|m\.?tech|m\.?s|phd|mba)$", re.IGNORECASE),
]

_BATCH_YEAR_REGEX = re.compile(r"^(?:batch\s+)?(20\d{2})$", re.IGNORECASE)


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


def parse_academic_year(raw_val: Any) -> tuple[Optional[str], Optional[int], Optional[str]]:
    """Parse and normalize academic year of study or batch.

    Returns:
        (normalized_label, year_number, error_message)
    """
    if raw_val is None:
        return None, None, None

    text = str(raw_val).strip()
    if not text:
        return None, None, None

    # Check standard year patterns (1st - 5th)
    for pattern, label, yr_num in _YEAR_PATTERNS:
        if pattern.match(text):
            return label, yr_num, None

    # Check graduation year (e.g. 2026)
    batch_match = _BATCH_YEAR_REGEX.match(text)
    if batch_match:
        year_str = batch_match.group(1)
        return f"Batch {year_str}", int(year_str), None

    # Check postgraduate patterns
    for pattern in _GRAD_PATTERNS:
        if pattern.match(text):
            return "Postgraduate", None, None

    return None, None, f"Unrecognized academic year format: '{text}'."


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

        # Resolve raw CGPA / CPI value and source field name
        cgpa_val, cgpa_field_name = self._resolve_cgpa_value(member, cfg)

        # Resolve raw Academic Year value and source field name
        year_val, year_field_name = self._resolve_year_value(member, cfg)

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
                        error_message="Academic score (CGPA/CPI) was not provided.",
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
                            source="registration_data",
                            raw_input=str(cgpa_val),
                            metadata={"source_field": cgpa_field_name, "error": score_err},
                        ),
                    )
                )
            else:
                results.append(
                    ExtractedSignal(
                        signal_key="academic_cgpa",
                        category="academic",
                        value=score,
                        status=SignalStatus.EXTRACTED,
                        evidence=SignalEvidence(
                            source="registration_data",
                            raw_input=str(cgpa_val),
                            extracted_at=timestamp,
                            confidence=1.0,
                            metadata={
                                "raw_value": str(cgpa_val),
                                "numeric_score": score,
                                "scale": scale,
                                "system": system,
                                "source_field": cgpa_field_name,
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
                            source="registration_data",
                            raw_input=str(cgpa_val),
                            metadata={"source_field": cgpa_field_name, "error": score_err},
                        ),
                    )
                )
            elif scale == 10.0:
                results.append(
                    ExtractedSignal(
                        signal_key="normalized_cgpa_10_scale",
                        category="academic",
                        value=score,
                        status=SignalStatus.EXTRACTED,
                        evidence=SignalEvidence(
                            source="registration_data",
                            raw_input=str(cgpa_val),
                            extracted_at=timestamp,
                            confidence=1.0,
                            metadata={
                                "raw_value": str(cgpa_val),
                                "normalized_score": score,
                                "original_scale": 10.0,
                                "target_scale": 10.0,
                                "source_field": cgpa_field_name,
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
                                source="registration_data",
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
                    results.append(
                        ExtractedSignal(
                            signal_key="normalized_cgpa_10_scale",
                            category="academic",
                            value=normalized_score,
                            status=SignalStatus.EXTRACTED,
                            evidence=SignalEvidence(
                                source="registration_data",
                                raw_input=str(cgpa_val),
                                extracted_at=timestamp,
                                confidence=0.9,
                                metadata={
                                    "raw_value": str(cgpa_val),
                                    "original_score": score,
                                    "original_scale": scale,
                                    "normalized_score": normalized_score,
                                    "target_scale": 10.0,
                                    "source_field": cgpa_field_name,
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
                        error_message="Academic year was not provided.",
                        evidence=SignalEvidence(
                            source="registration_data",
                            raw_input=None,
                            metadata={"reason": "missing_input", "source_field": year_field_name},
                        ),
                    )
                )
            else:
                norm_label, yr_num, yr_err = parse_academic_year(year_val)
                if yr_err or norm_label is None:
                    results.append(
                        ExtractedSignal(
                            signal_key="academic_year",
                            category="academic",
                            value=None,
                            status=SignalStatus.FAILED,
                            error_message=yr_err or "Invalid academic year format.",
                            evidence=SignalEvidence(
                                source="registration_data",
                                raw_input=str(year_val),
                                metadata={"source_field": year_field_name, "error": yr_err},
                            ),
                        )
                    )
                else:
                    results.append(
                        ExtractedSignal(
                            signal_key="academic_year",
                            category="academic",
                            value=norm_label,
                            status=SignalStatus.EXTRACTED,
                            evidence=SignalEvidence(
                                source="registration_data",
                                raw_input=str(year_val),
                                extracted_at=timestamp,
                                confidence=1.0,
                                metadata={
                                    "raw_value": str(year_val),
                                    "normalized_year": norm_label,
                                    "year_number": yr_num,
                                    "source_field": year_field_name,
                                },
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
