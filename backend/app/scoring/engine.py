"""Deterministic weighted scoring and team-level aggregation engine.

Evaluates teams and their extracted signals against an immutable scoring configuration.
Computes explainable, normalized team scores in [0.0, scale_max] (default 0–100).

Core Invariants:
1. Pure calculation: Never invokes network analyzers or external APIs directly.
2. Relative weight normalization: Automatically renormalizes enabled weights to sum to 1.0.
3. Strict numeric safety: Rejects booleans, NaN, and infinity; preserves legitimate zero (0, 0.0).
4. Explicit missing-data semantics:
   - EXCLUDE_AND_RENORMALIZE: Drops criterion from denominator; renormalizes remaining weights.
   - ZERO_SCORE: Imputes 0.0 score while keeping criterion in denominator.
   - If no criteria are evaluable: Returns NO_SCORE rather than an invented zero.
5. Aggregation safety: Clamps sum to 1.0; supports mean, min, max, lead_only, and top_k.
6. Clean eligibility separation: Preserves eligibility status without mutating it or re-evaluating rules.
"""

from __future__ import annotations

import datetime
import math
import re
import uuid
from typing import Any, Optional

from app.rules.schemas import EligibilityStatus
from app.rules.store import default_run_store, get_effective_run
from app.schemas.ingestion import KNOWN_MEMBER_FIELDS, MemberSchema, TeamSchema
from app.scoring.schemas import (
    AggregationMethod,
    CriterionScoreBreakdown,
    CriterionType,
    EvaluationCriterion,
    MemberScoreDetail,
    MissingDataPolicy,
    ScoreStatus,
    ScoringConfiguration,
    ScoringRunResponse,
    ScoringRunSummary,
    TeamScoringResult,
)
from app.signals.schemas import ExtractedSignal, SignalStatus


# ---------------------------------------------------------------------------
# Helpers: Field, Signal, and Numeric Safety
# ---------------------------------------------------------------------------


def parse_numeric_safely(val: Any) -> tuple[Optional[float], bool]:
    """Parse a numeric value with strict type and domain safety.

    Rejects:
    - Booleans (bool is a subclass of int in Python)
    - NaN (math.isnan)
    - Infinity / -Infinity (math.isinf)
    - Non-numeric strings or non-numeric types

    Accepts:
    - 0, 0.0 (Zero is valid and preserved)
    - Finite float and integer numbers
    """
    if isinstance(val, bool):
        return None, False

    if isinstance(val, (int, float)):
        if math.isnan(val) or math.isinf(val):
            return None, False
        return float(val), True

    if isinstance(val, str):
        clean = val.strip()
        if not clean:
            return None, False
        try:
            num = float(clean)
            if math.isnan(num) or math.isinf(num):
                return None, False
            return num, True
        except (ValueError, TypeError):
            return None, False

    return None, False


def compute_field_confidence(target: str, candidate_key: str) -> float:
    """Calculate fuzzy/token similarity confidence between a target field name and a candidate column."""
    t = target.lower().replace("custom:", "").replace("custom_", "").strip()
    c = candidate_key.lower().replace("custom:", "").replace("custom_", "").strip()
    if not t or not c:
        return 0.0
    if t == c:
        return 1.0

    t_stem = t.rstrip("s")
    c_stem = c.rstrip("s")
    if t_stem == c_stem:
        return 0.98

    # Token overlap
    t_tokens = set(re.split(r"[_\s\-]+", t))
    c_tokens = set(re.split(r"[_\s\-]+", c))
    if t_tokens and c_tokens:
        overlap = t_tokens & c_tokens
        if overlap:
            jaccard = len(overlap) / len(t_tokens | c_tokens)
            if t in c_tokens or t_stem in {tok.rstrip("s") for tok in c_tokens}:
                return max(0.85, 0.80 + 0.15 * jaccard)
            return 0.75 + 0.20 * jaccard

    # Substring root containment
    if len(t_stem) >= 3:
        if t_stem in c or c_stem in t:
            len_ratio = min(len(t_stem), len(c_stem)) / max(len(t_stem), len(c_stem))
            if len_ratio >= 0.5:
                return 0.80 + 0.15 * len_ratio

    return 0.0


def resolve_member_signal_or_field(
    member: MemberSchema,
    signal_key: str,
    signals_by_member: dict[str, dict[str, ExtractedSignal]],
) -> tuple[Any, Optional[str], Optional[str], Optional[float]]:
    """Retrieve raw value, status, provenance, and confidence for a member and signal key.

    Returns:
        (raw_value, signal_status_str, provenance, confidence)
    """
    # 1. Check pre-extracted signals payload
    m_signals = signals_by_member.get(member.member_id, {})
    raw_k = signal_key.split(":", 1)[1] if ":" in signal_key else signal_key
    target_keys = (signal_key, raw_k, f"custom:{raw_k}", f"custom_{raw_k}")

    for k in target_keys:
        if k in m_signals:
            sig = m_signals[k]
            provenance = sig.evidence.source if sig.evidence else None
            confidence = sig.evidence.confidence if sig.evidence else None

            if sig.status == SignalStatus.EXTRACTED:
                return sig.value, "extracted", provenance, confidence
            elif sig.status == SignalStatus.NOT_APPLICABLE:
                return None, "not_applicable", provenance, confidence
            elif sig.status == SignalStatus.FAILED:
                return None, "failed", provenance, confidence
            elif sig.status == SignalStatus.PENDING:
                return None, "pending", provenance, confidence
            elif sig.status == SignalStatus.SKIPPED:
                return None, "skipped", provenance, confidence
            return sig.value, sig.status.value, provenance, confidence

    # 2. Fallback: Check custom_fields
    for k in target_keys:
        if k in member.custom_fields:
            val = member.custom_fields[k]
            if val is not None and not (isinstance(val, str) and not val.strip()):
                return val, "extracted", "registration_custom_fields", 0.85
            return None, "not_applicable", "registration_custom_fields", 0.85

    # 3. Fallback: Check raw_data
    for k in target_keys:
        if k in member.raw_data:
            val = member.raw_data[k]
            if val is not None and not (isinstance(val, str) and not val.strip()):
                return val, "extracted", "registration_raw_data", 0.85
            return None, "not_applicable", "registration_raw_data", 0.85

    # 4. Fallback: Check canonical MemberSchema attribute
    if signal_key in KNOWN_MEMBER_FIELDS:
        val = getattr(member, signal_key, None)
        if val is not None and not (isinstance(val, str) and not val.strip()):
            return val, "extracted", "registration_canonical", 1.0
        return None, "not_applicable", "registration_canonical", 1.0

    # 5. Fallback: Fuzzy / Confidence matching for custom signals against available candidate fields (threshold >= 0.80)
    best_key = None
    best_conf = 0.0
    best_val = None
    best_source = None

    candidates = [
        (member.custom_fields, "registration_custom_fields"),
        (member.raw_data, "registration_raw_data"),
    ]
    for c_dict, src_name in candidates:
        for k, v in c_dict.items():
            if v is not None and not (isinstance(v, str) and not v.strip()):
                conf = compute_field_confidence(raw_k, k)
                if conf > best_conf:
                    best_conf = conf
                    best_key = k
                    best_val = v
                    best_source = src_name

    for k, sig in m_signals.items():
        if sig.status == SignalStatus.EXTRACTED and sig.value is not None:
            conf = compute_field_confidence(raw_k, k)
            if conf > best_conf:
                best_conf = conf
                best_key = k
                best_val = sig.value
                best_source = sig.evidence.source if sig.evidence else "extracted_signal"

    if best_conf >= 0.80 and best_val is not None:
        effective_conf = round(best_conf, 2)
        return best_val, "extracted", f"{best_source}:{best_key}", effective_conf

    return None, "unavailable", None, None


# ---------------------------------------------------------------------------
# Normalization Calculation
# ---------------------------------------------------------------------------


def normalize_value(
    raw_val: Any,
    criterion: EvaluationCriterion,
) -> tuple[Optional[float], str]:
    """Normalize a raw value to a float score in [0.0, 1.0].

    Returns:
        (normalized_score, explanation_detail)
        If raw_val cannot be normalized, returns (None, reason).
    """
    if raw_val is None:
        return None, "Value is None"

    ctype = criterion.criterion_type

    # A. NUMERIC RANGE
    if ctype in (CriterionType.NUMERIC_RANGE, CriterionType.NUMERIC_WEIGHT):
        num_val, is_valid = parse_numeric_safely(raw_val)
        if not is_valid or num_val is None:
            return None, f"Invalid numeric value '{raw_val}'"

        lr = criterion.normalization.linear_range
        if lr is None:
            return None, "Missing linear_range configuration"

        min_v = lr.min_value
        max_v = lr.max_value

        if num_val <= min_v:
            norm = 0.0
        elif num_val >= max_v:
            norm = 1.0
        else:
            norm = (num_val - min_v) / (max_v - min_v)

        # Apply optional confidence adjustment if enabled
        ca = criterion.confidence_adjustment
        if ca and ca.enabled:
            # Caller handles confidence multiplier after lookup
            pass

        return norm, f"Linearly mapped {num_val} to [{min_v}, {max_v}] -> {round(norm, 4)}"

    # B. BOOLEAN
    elif ctype in (CriterionType.BOOLEAN, CriterionType.BOOLEAN_BONUS):
        bm = criterion.normalization.boolean_mapping
        true_score = bm.true_score if bm else 1.0
        false_score = bm.false_score if bm else 0.0

        if isinstance(raw_val, bool):
            score = true_score if raw_val else false_score
            return score, f"Boolean {raw_val} mapped to {score}"

        if isinstance(raw_val, str):
            s_clean = raw_val.strip().lower()
            if s_clean in ("true", "yes", "1"):
                return true_score, f"Boolean True mapped to {true_score}"
            elif s_clean in ("false", "no", "0"):
                return false_score, f"Boolean False mapped to {false_score}"

        return None, f"Value '{raw_val}' is not a valid boolean"

    # C. CATEGORICAL & GENERALIZED VALUE/KEYWORD MATCHING
    elif ctype in (CriterionType.CATEGORICAL, CriterionType.CATEGORY_MATCH):
        cm = criterion.normalization.categorical_mapping
        category_map = cm.category_scores if cm else {}

        val_str = str(raw_val).strip()

        # 1. Direct discrete category match (case-sensitive or case-insensitive)
        if category_map:
            if cm and not cm.case_sensitive:
                lower_map = {k.lower(): v for k, v in category_map.items()}
                match_key = val_str.lower()
                if match_key in lower_map:
                    score = lower_map[match_key]
                    return score, f"Category '{val_str}' mapped to {score}"
            else:
                if val_str in category_map:
                    score = category_map[val_str]
                    return score, f"Category '{val_str}' mapped to {score}"

        # 2. Generalized Keyword / Desired Value Matching
        # Used for custom recruitment signals, skill lists, comma-separated tokens, or when expected_values is configured
        expected_items: list[str] = []
        if criterion.config and criterion.config.get("expected_values"):
            cfg_vals = criterion.config["expected_values"]
            if isinstance(cfg_vals, list):
                expected_items = [str(x).strip() for x in cfg_vals if str(x).strip()]
            elif isinstance(cfg_vals, str):
                expected_items = [str(x).strip() for x in re.split(r"[,;|/\n\r]+", cfg_vals) if str(x).strip()]

        if not expected_items and category_map:
            # Fall back to keys in category_map if multiple or custom
            expected_items = [str(x).strip() for x in category_map.keys() if str(x).strip()]

        if expected_items:
            # Tokenize / parse candidate's raw value
            if isinstance(raw_val, (list, tuple, set)):
                cand_tokens = [str(x).strip().lower() for x in raw_val if str(x).strip()]
                cand_text = " ".join(cand_tokens)
            else:
                cand_tokens = [t.strip().lower() for t in re.split(r"[,;|/\n\r]+", val_str) if t.strip()]
                cand_text = val_str.lower()

            matched_items: list[str] = []
            words = [w.strip(".,!?:;\"'()[]{}").lower() for w in val_str.split() if w.strip()]
            for item in expected_items:
                item_clean = item.strip()
                item_lower = item_clean.lower()
                if item_lower in cand_tokens or item_lower in words:
                    matched_items.append(item_clean)
                else:
                    pattern = r"(?:^|[\s,;|/(\[{<\"'])" + re.escape(item_lower) + r"(?:$|[\s,;|/.)\]}>\"':!?])"
                    if re.search(pattern, cand_text, re.IGNORECASE):
                        matched_items.append(item_clean)

            match_mode = (criterion.config.get("match_mode") or "proportional").lower() if criterion.config else "proportional"
            total = len(expected_items)
            k = len(matched_items)

            if match_mode == "any":
                score = 1.0 if k > 0 else (cm.default_score if cm and cm.default_score is not None else 0.0)
                matched_str = ", ".join(matched_items) if matched_items else "none"
                return score, f"Matched {k} expected item(s) ({matched_str}) -> score: {round(score, 4)}"
            else:
                score = k / total if total > 0 else 0.0
                if k == 0 and cm and cm.default_score is not None:
                    score = cm.default_score
                matched_str = ", ".join(matched_items) if matched_items else "none"
                return score, f"Matched {k} of {total} expected item(s) ({matched_str}) -> score: {round(score, 4)}"

        # 3. Default fallback score if configured
        if cm and cm.default_score is not None:
            return cm.default_score, f"Unlisted category '{val_str}' mapped to default {cm.default_score}"

        return None, f"Category '{val_str}' not found in allowed category scores or expected values"

    return None, f"Unsupported criterion type '{ctype}'"


# ---------------------------------------------------------------------------
# Aggregation Calculation
# ---------------------------------------------------------------------------


def aggregate_member_scores(
    member_details: list[MemberScoreDetail],
    criterion: EvaluationCriterion,
    team: TeamSchema,
    config: ScoringConfiguration,
) -> tuple[Optional[float], list[MemberScoreDetail], str]:
    """Aggregate member-level normalized scores to a team criterion score in [0.0, 1.0].

    Returns:
        (aggregated_score, updated_member_details, explanation)
    """
    valid_members = [m for m in member_details if m.normalized_score is not None]

    if not valid_members:
        return None, member_details, "No valid member scores to aggregate"

    method = criterion.aggregation

    # 1. MEAN
    if method == AggregationMethod.MEAN:
        scores = [m.normalized_score for m in valid_members if m.normalized_score is not None]
        avg = sum(scores) / len(scores)
        return avg, member_details, f"Average of {len(scores)} valid member scores: {round(avg, 4)}"

    # 2. MIN
    elif method == AggregationMethod.MIN:
        scores = [m.normalized_score for m in valid_members if m.normalized_score is not None]
        val = min(scores)
        return val, member_details, f"Minimum of {len(scores)} valid member scores: {round(val, 4)}"

    # 3. MAX
    elif method == AggregationMethod.MAX:
        scores = [m.normalized_score for m in valid_members if m.normalized_score is not None]
        val = max(scores)
        return val, member_details, f"Maximum of {len(scores)} valid member scores: {round(val, 4)}"

    # 4. SUM (Capped at 1.0 for bounds safety)
    elif method == AggregationMethod.SUM:
        scores = [m.normalized_score for m in valid_members if m.normalized_score is not None]
        raw_sum = sum(scores)
        clamped = min(1.0, raw_sum)
        exp = f"Sum of {len(scores)} member scores (raw: {round(raw_sum, 4)}, clamped to max 1.0): {round(clamped, 4)}"
        return clamped, member_details, exp

    # 5. LEAD ONLY
    elif method == AggregationMethod.LEAD_ONLY:
        lead_field = config.lead_field or "role"
        lead_values = [v.lower() for v in config.lead_values]

        lead_member_id: Optional[str] = None
        for member in team.members:
            # Check custom_fields, raw_data, canonical
            m_val = (
                member.custom_fields.get(lead_field)
                or member.raw_data.get(lead_field)
                or getattr(member, lead_field, None)
            )
            if m_val and str(m_val).strip().lower() in lead_values:
                lead_member_id = member.member_id
                break

        if not lead_member_id:
            # Mark all as non-contributing
            for m in member_details:
                m.is_contributing = False
                m.exclusion_reason = f"Designated team lead could not be determined using field '{lead_field}'"
            return None, member_details, f"Designated team lead could not be determined using field '{lead_field}'"

        # Find lead's score
        lead_detail = next((m for m in member_details if m.member_id == lead_member_id), None)
        for m in member_details:
            if m.member_id != lead_member_id:
                m.is_contributing = False
                m.exclusion_reason = "Non-lead member excluded by lead_only policy"

        if lead_detail and lead_detail.normalized_score is not None:
            return lead_detail.normalized_score, member_details, f"Team lead ({lead_detail.member_name}) score"
        return None, member_details, "Team lead lacked valid score for this criterion"

    # 6. TOP K
    elif method == AggregationMethod.TOP_K:
        k = criterion.top_k_value or 1
        sorted_members = sorted(
            valid_members,
            key=lambda m: m.normalized_score if m.normalized_score is not None else -1.0,
            reverse=True,
        )
        top_slice = sorted_members[:k]
        top_ids = {m.member_id for m in top_slice}

        for m in member_details:
            if m.member_id not in top_ids and m.normalized_score is not None:
                m.is_contributing = False
                m.exclusion_reason = f"Excluded outside top {k} member scores"

        scores = [m.normalized_score for m in top_slice if m.normalized_score is not None]
        avg = sum(scores) / len(scores)
        return avg, member_details, f"Average of top {len(scores)} member scores (K={k}): {round(avg, 4)}"

    return None, member_details, f"Unsupported aggregation method '{method}'"


# ---------------------------------------------------------------------------
# Core Evaluation Engine
# ---------------------------------------------------------------------------


def evaluate_team_criteria(
    team: TeamSchema,
    config: ScoringConfiguration,
    signals_by_member: dict[str, dict[str, ExtractedSignal]],
) -> tuple[list[CriterionScoreBreakdown], list[str]]:
    """Evaluate all enabled criteria for a single team.

    Returns:
        (criteria_breakdowns, warnings)
    """
    breakdowns: list[CriterionScoreBreakdown] = []
    warnings: list[str] = []

    for criterion in config.criteria:
        if not criterion.is_enabled:
            continue

        raw_values: dict[str, Any] = {}
        signal_statuses: dict[str, str] = {}
        member_details: list[MemberScoreDetail] = []

        for member in team.members:
            raw_v, status_str, prov, conf = resolve_member_signal_or_field(
                member=member,
                signal_key=criterion.target_signal_key,
                signals_by_member=signals_by_member,
            )
            raw_values[member.member_id] = raw_v
            signal_statuses[member.member_id] = status_str or "unknown"

            norm_score: Optional[float] = None
            exclusion_reason: Optional[str] = None

            if status_str == "extracted" and raw_v is not None:
                n_score, exp_norm = normalize_value(raw_v, criterion)
                if n_score is not None:
                    # Apply confidence adjustment if enabled
                    ca = criterion.confidence_adjustment
                    if ca and ca.enabled:
                        if conf is not None:
                            if ca.min_confidence is not None and conf < ca.min_confidence:
                                n_score = None
                                exclusion_reason = f"Confidence {conf} below required threshold {ca.min_confidence}"
                            else:
                                n_score = n_score * conf
                        else:
                            # Confidence not available
                            pass
                    norm_score = n_score
                else:
                    exclusion_reason = exp_norm
            else:
                exclusion_reason = f"Signal status '{status_str}' or value missing"

            member_details.append(
                MemberScoreDetail(
                    member_id=member.member_id,
                    member_name=member.name,
                    raw_value=raw_v,
                    signal_status=status_str,
                    provenance=prov,
                    confidence=conf,
                    normalized_score=norm_score,
                    is_contributing=(norm_score is not None),
                    exclusion_reason=exclusion_reason,
                )
            )

        # Aggregate member scores
        team_score, updated_details, agg_exp = aggregate_member_scores(
            member_details=member_details,
            criterion=criterion,
            team=team,
            config=config,
        )

        missing_applied = False
        is_applicable = True
        explanation = agg_exp

        if team_score is None:
            # Handle missing data according to configured policy
            if criterion.missing_data_policy == MissingDataPolicy.ZERO_SCORE:
                team_score = 0.0
                missing_applied = True
                explanation = f"Normalized score 0.0 assigned by policy (ZERO_SCORE): {agg_exp}."
            else:
                # EXCLUDE_AND_RENORMALIZE
                is_applicable = False
                missing_applied = True
                explanation = f"Excluded from denominator by policy (EXCLUDE_AND_RENORMALIZE): {agg_exp}."

        breakdowns.append(
            CriterionScoreBreakdown(
                criterion_id=criterion.criterion_id,
                name=criterion.name,
                target_signal_key=criterion.target_signal_key,
                criterion_type=criterion.criterion_type,
                configured_weight=criterion.weight,
                normalized_weight=0.0,  # Computed at team level across applicable criteria
                raw_values=raw_values,
                signal_statuses=signal_statuses,
                normalization_method=criterion.criterion_type.value,
                aggregation_method=criterion.aggregation.value,
                team_criterion_score=team_score,
                weighted_contribution=0.0,  # Computed at team level
                missing_data_policy=criterion.missing_data_policy,
                is_applicable=is_applicable,
                missing_data_applied=missing_applied,
                member_scores=updated_details,
                explanation=explanation,
            )
        )

    return breakdowns, warnings


def calculate_team_score(
    team: TeamSchema,
    config: ScoringConfiguration,
    signals_by_member: dict[str, dict[str, ExtractedSignal]],
    eligibility_status: Optional[EligibilityStatus] = None,
    eligibility_summary: Optional[str] = None,
) -> TeamScoringResult:
    """Compute composite weighted score, breakdowns, and audit details for a team."""
    # Empty team check
    if not team.members:
        return TeamScoringResult(
            team_id=team.team_id,
            team_name=team.team_name,
            final_score=None,
            score_status=ScoreStatus.NO_SCORE,
            total_configured_weight=sum(c.weight for c in config.criteria if c.is_enabled),
            applicable_weight=0.0,
            weight_renormalized=False,
            criteria_breakdowns=[],
            eligibility_status=eligibility_status,
            eligibility_summary=eligibility_summary,
            warnings=["Team has 0 members; cannot evaluate scores."],
            explanation="Empty team has no members to evaluate.",
        )

    # Disqualified team check (if score_ineligible_teams is False and team is INELIGIBLE)
    if not config.score_ineligible_teams and eligibility_status == EligibilityStatus.INELIGIBLE:
        return TeamScoringResult(
            team_id=team.team_id,
            team_name=team.team_name,
            final_score=0.0,
            score_status=ScoreStatus.DISQUALIFIED,
            total_configured_weight=sum(c.weight for c in config.criteria if c.is_enabled),
            applicable_weight=0.0,
            weight_renormalized=False,
            criteria_breakdowns=[],
            eligibility_status=eligibility_status,
            eligibility_summary=eligibility_summary,
            warnings=["Score suppressed because team is INELIGIBLE."],
            explanation=f"Team is INELIGIBLE ({eligibility_summary or 'Hard rule violation'}). Score suppressed to 0.0.",
        )

    # Evaluate criteria
    breakdowns, warnings = evaluate_team_criteria(team, config, signals_by_member)

    total_configured_weight = sum(b.configured_weight for b in breakdowns)
    applicable_breakdowns = [b for b in breakdowns if b.is_applicable and b.team_criterion_score is not None]
    applicable_weight = sum(b.configured_weight for b in applicable_breakdowns)

    # No evaluable criteria available
    if not applicable_breakdowns or applicable_weight <= 0.0:
        return TeamScoringResult(
            team_id=team.team_id,
            team_name=team.team_name,
            final_score=None,
            score_status=ScoreStatus.NO_SCORE,
            total_configured_weight=total_configured_weight,
            applicable_weight=0.0,
            weight_renormalized=False,
            criteria_breakdowns=breakdowns,
            eligibility_status=eligibility_status,
            eligibility_summary=eligibility_summary,
            warnings=warnings + ["No evaluable criteria available for this team."],
            explanation="No evaluable criteria available for this team; score cannot be calculated.",
        )

    # Relative weight renormalization
    weight_renormalized = applicable_weight < total_configured_weight
    total_contribution = 0.0

    for b in breakdowns:
        if b.is_applicable and b.team_criterion_score is not None:
            norm_weight = b.configured_weight / applicable_weight
            contribution = b.team_criterion_score * norm_weight * config.scale_max
            b.normalized_weight = round(norm_weight, 6)
            b.weighted_contribution = round(contribution, 4)
            total_contribution += contribution
        else:
            b.normalized_weight = 0.0
            b.weighted_contribution = 0.0

    final_score = round(total_contribution, 2)
    # Ensure bounds [0.0, scale_max]
    final_score = max(0.0, min(config.scale_max, final_score))

    explanation = (
        f"Composite score: {final_score:.2f} / {config.scale_max:.0f}. "
        f"Evaluated {len(applicable_breakdowns)} of {len(breakdowns)} criteria. "
        f"Applicable weight: {applicable_weight:.1f} / {total_configured_weight:.1f}."
    )
    if weight_renormalized:
        explanation += " (Remaining criterion weights were renormalized)."

    return TeamScoringResult(
        team_id=team.team_id,
        team_name=team.team_name,
        final_score=final_score,
        score_status=ScoreStatus.CALCULATED,
        total_configured_weight=total_configured_weight,
        applicable_weight=applicable_weight,
        weight_renormalized=weight_renormalized,
        criteria_breakdowns=breakdowns,
        eligibility_status=eligibility_status,
        eligibility_summary=eligibility_summary,
        warnings=warnings,
        explanation=explanation,
    )


def evaluate_scoring(
    teams: list[Any],
    signals: Optional[list[dict[str, Any]]],
    config: ScoringConfiguration,
    eligibility_run_id: Optional[str] = None,
    eligibility_results: Optional[list[dict[str, Any]]] = None,
    evaluated_at: Optional[str] = None,
    run_id: Optional[str] = None,
) -> ScoringRunResponse:
    """Execute weighted scoring evaluation for a list of teams.

    Args:
        teams: List of TeamSchema instances or raw dictionaries.
        signals: Optional pre-extracted signals per member.
        config: ScoringConfiguration with criteria and scale_max.
        eligibility_run_id: Optional ID of an eligibility run to pull statuses from default_run_store.
        eligibility_results: Optional explicit eligibility result dicts.
        evaluated_at: Optional injected ISO timestamp for deterministic testing.
        run_id: Optional injected run identifier for deterministic testing.

    Returns:
        Standardized ScoringRunResponse with sorted team results and summary metrics.
    """
    final_run_id = run_id or f"score_run_{uuid.uuid4().hex[:12]}"
    now_ts = evaluated_at or datetime.datetime.now(datetime.timezone.utc).isoformat()

    warnings: list[str] = []
    errors: list[str] = []

    # Map signals by member_id -> signal_key -> ExtractedSignal
    signals_by_member: dict[str, dict[str, ExtractedSignal]] = {}
    if signals:
        for s_item in signals:
            if isinstance(s_item, dict):
                m_id = str(s_item.get("member_id", ""))
                sig_list = s_item.get("signals", [])
            else:
                m_id = getattr(s_item, "member_id", "")
                sig_list = getattr(s_item, "signals", [])

            member_map = signals_by_member.setdefault(m_id, {})
            for sig in sig_list:
                if isinstance(sig, ExtractedSignal):
                    member_map[sig.signal_key] = sig
                elif isinstance(sig, dict):
                    try:
                        validated_sig = ExtractedSignal.model_validate(sig)
                        member_map[validated_sig.signal_key] = validated_sig
                    except Exception:
                        pass

    # Map eligibility outcomes if provided
    eligibility_by_team: dict[str, tuple[Optional[EligibilityStatus], Optional[str]]] = {}

    if eligibility_results:
        for er in eligibility_results:
            t_id = str(er.get("team_id", ""))
            st_raw = er.get("status")
            status_enum = None
            if st_raw:
                try:
                    status_enum = EligibilityStatus(st_raw)
                except Exception:
                    pass
            summ = er.get("summary") or er.get("explanation")
            if not summ and er.get("reasons"):
                reasons = er.get("reasons")
                if isinstance(reasons, list):
                    summ = "; ".join(str(r) for r in reasons) or None
                elif isinstance(reasons, str):
                    summ = reasons
            eligibility_by_team[t_id] = (status_enum, summ)

    elif eligibility_run_id:
        cached_elig = get_effective_run(eligibility_run_id)
        if cached_elig:
            for t_res in cached_elig.teams:
                summary_text = "; ".join(t_res.reasons) or None
                eligibility_by_team[t_res.team_id] = (t_res.status, summary_text)
        else:
            warnings.append(f"Eligibility run '{eligibility_run_id}' not found in store; continuing without eligibility.")

    team_results: list[TeamScoringResult] = []

    for idx, team_raw in enumerate(teams):
        team_obj: Optional[TeamSchema] = None
        if isinstance(team_raw, TeamSchema):
            team_obj = team_raw
        elif isinstance(team_raw, dict):
            try:
                team_obj = TeamSchema.model_validate(team_raw)
            except Exception as ex:
                raw_id = str(team_raw.get("team_id", f"malformed_team_{idx}"))
                raw_name = str(team_raw.get("team_name", "Invalid Team"))
                team_results.append(
                    TeamScoringResult(
                        team_id=raw_id,
                        team_name=raw_name,
                        final_score=None,
                        score_status=ScoreStatus.NO_SCORE,
                        total_configured_weight=sum(c.weight for c in config.criteria if c.is_enabled),
                        applicable_weight=0.0,
                        weight_renormalized=False,
                        criteria_breakdowns=[],
                        warnings=[f"Failed to parse team: {str(ex)}"],
                        explanation=f"Malformed team record could not be parsed: {str(ex)}",
                    )
                )
                errors.append(f"Team {raw_id}: schema validation failed.")
                continue

        if team_obj is None:
            continue

        elig_status, elig_summary = eligibility_by_team.get(team_obj.team_id, (None, None))
        res = calculate_team_score(
            team=team_obj,
            config=config,
            signals_by_member=signals_by_member,
            eligibility_status=elig_status,
            eligibility_summary=elig_summary,
        )
        team_results.append(res)

    # Sort deterministically by team_id
    team_results.sort(key=lambda t: t.team_id)

    # Compute summary metrics
    total_teams = len(team_results)
    calculated_teams = sum(1 for t in team_results if t.score_status == ScoreStatus.CALCULATED)
    no_score_teams = sum(1 for t in team_results if t.score_status == ScoreStatus.NO_SCORE)
    disqualified_teams = sum(1 for t in team_results if t.score_status == ScoreStatus.DISQUALIFIED)
    needs_review_teams = sum(1 for t in team_results if t.score_status == ScoreStatus.NEEDS_REVIEW)

    valid_scores = [t.final_score for t in team_results if t.final_score is not None]
    avg_score = round(sum(valid_scores) / len(valid_scores), 2) if valid_scores else None
    min_score = min(valid_scores) if valid_scores else None
    max_score = max(valid_scores) if valid_scores else None

    summary = ScoringRunSummary(
        total_teams=total_teams,
        calculated_teams=calculated_teams,
        no_score_teams=no_score_teams,
        disqualified_teams=disqualified_teams,
        needs_review_teams=needs_review_teams,
        average_score=avg_score,
        min_score=min_score,
        max_score=max_score,
    )

    return ScoringRunResponse(
        run_id=final_run_id,
        config_id=config.config_id,
        config_version=config.version,
        evaluated_at=now_ts,
        teams=team_results,
        summary=summary,
        warnings=warnings,
        errors=errors,
    )
