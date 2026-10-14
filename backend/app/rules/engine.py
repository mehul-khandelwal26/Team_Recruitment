"""Deterministic eligibility rules evaluation engine.

Evaluates teams and their members against an immutable, versioned rule configuration.
Produces an explicit, human-readable audit trail per rule and an overall team decision:
- ELIGIBLE
- INELIGIBLE
- NEEDS_REVIEW

Architecture Semantics:
1. Contradiction Resolution:
   - SignalStatus.NOT_APPLICABLE = NOT PROVIDED (evaluates as FAILED on rules requiring that signal).
   - SignalStatus.FAILED / PENDING / SKIPPED / absent payload = UNAVAILABLE (triggers on_missing).
2. Numeric Safety:
   - Rejects bool (e.g. True/False), NaN, and infinity as invalid (UNAVAILABLE).
   - Validates and preserves zero (0, 0.0) as legitimate numeric data.
3. Field Lookup Precedence:
   - custom_fields -> raw_data -> canonical MemberSchema attributes.
4. Fault Isolation:
   - Individual invalid teams receive a structured error result; the run continues.
   - Evaluated teams are deterministically sorted by team_id.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Optional

from app.rules.schemas import (
    EligibilityRunResponse,
    EligibilityRunSummary,
    EligibilityStatus,
    MemberSignals,
    RuleConfiguration,
    RuleResult,
    RuleResultStatus,
    RuleSeverity,
    TeamEligibilityResult,
)
from app.rules.types import get_evaluator
from app.schemas.ingestion import TeamSchema
from app.signals.schemas import ExtractedSignal


def evaluate_teams(
    teams: list[Any],
    signals: list[MemberSignals] | list[dict[str, Any]] | None,
    config: RuleConfiguration,
    evaluated_at: Optional[str] = None,
    run_id: Optional[str] = None,
) -> EligibilityRunResponse:
    """Execute deterministic eligibility evaluation for a collection of teams.

    Args:
        teams: List of TeamSchema instances or raw team dictionaries.
        signals: Optional pre-extracted signals per member. The engine never calls analyzers.
        config: Versioned RuleConfiguration containing rules and global_config.
        evaluated_at: Optional injected ISO timestamp for deterministic testing.
        run_id: Optional injected run identifier for deterministic testing.

    Returns:
        Standardized EligibilityRunResponse with sorted team results and summary metrics.
    """
    final_run_id = run_id or f"run_{uuid.uuid4().hex[:12]}"
    now_ts = evaluated_at or datetime.datetime.now(datetime.timezone.utc).isoformat()

    warnings: list[str] = []
    errors: list[str] = []

    # Map signals by member_id -> signal_key -> ExtractedSignal
    signals_by_member: dict[str, dict[str, ExtractedSignal]] = {}
    if signals:
        for s_item in signals:
            if isinstance(s_item, MemberSignals):
                m_id = s_item.member_id
                sig_list = s_item.signals
            elif isinstance(s_item, dict):
                m_id = str(s_item.get("member_id", ""))
                sig_list = s_item.get("signals", [])
            else:
                continue

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

    # Sort active rules by order
    sorted_rules = sorted(
        [r for r in config.rules if r.is_enabled],
        key=lambda r: r.order,
    )

    team_results: list[TeamEligibilityResult] = []
    eligible_count = 0
    ineligible_count = 0
    needs_review_count = 0
    error_count = 0
    # Pre-collect valid teams for cross-team rules (e.g. duplicate_member_email, track_limit)
    valid_teams: list[TeamSchema] = []
    for team_raw in teams:
        if isinstance(team_raw, TeamSchema):
            valid_teams.append(team_raw)
        elif isinstance(team_raw, dict):
            try:
                valid_teams.append(TeamSchema.model_validate(team_raw))
            except Exception:
                pass

    for idx, team_raw in enumerate(teams):
        # 1. Validate team input into TeamSchema (Fault isolation)
        team_obj: Optional[TeamSchema] = None
        if isinstance(team_raw, TeamSchema):
            team_obj = team_raw
        elif isinstance(team_raw, dict):
            try:
                team_obj = TeamSchema.model_validate(team_raw)
            except Exception as exc:
                t_id = str(team_raw.get("team_id") or f"invalid_team_{idx}")
                t_name = str(team_raw.get("team_name") or f"Invalid Team {idx}")
                err_msg = f"Invalid team structure: {exc}"
                errors.append(err_msg)
                error_count += 1
                ineligible_count += 1
                team_results.append(
                    TeamEligibilityResult(
                        team_id=t_id,
                        team_name=t_name,
                        status=EligibilityStatus.INELIGIBLE,
                        reasons=[err_msg],
                        rule_results=[],
                        data_completeness=None,
                        errors=[err_msg],
                    )
                )
                continue
        else:
            t_id = f"unknown_team_{idx}"
            err_msg = f"Unsupported team input type: {type(team_raw)}"
            errors.append(err_msg)
            error_count += 1
            ineligible_count += 1
            team_results.append(
                TeamEligibilityResult(
                    team_id=t_id,
                    team_name="Unknown Team",
                    status=EligibilityStatus.INELIGIBLE,
                    reasons=[err_msg],
                    rule_results=[],
                    data_completeness=None,
                    errors=[err_msg],
                )
            )
            continue

        # 2. Evaluate all active rules against this team
        rule_results: list[RuleResult] = []
        evaluable_applicable_count = 0
        applicable_rules_count = len(sorted_rules)

        for rule in sorted_rules:
            evaluator = get_evaluator(rule.rule_type)
            if evaluator is None:
                err = f"Unrecognized rule type: '{rule.rule_type}'"
                warnings.append(err)
                rule_results.append(
                    RuleResult(
                        rule_id=rule.rule_id,
                        rule_type=rule.rule_type,
                        name=rule.name,
                        severity=rule.severity,
                        scope=rule.scope,
                        status=RuleResultStatus.ERROR,
                        explanation=err,
                        is_evaluable=False,
                    )
                )
                continue

            try:
                try:
                    res = evaluator.evaluate(
                        rule=rule,
                        team=team_obj,
                        signals_by_member=signals_by_member,
                        global_config=config.global_config,
                        all_teams=valid_teams,
                    )
                except TypeError as t_err:
                    if "all_teams" in str(t_err):
                        res = evaluator.evaluate(
                            rule=rule,
                            team=team_obj,
                            signals_by_member=signals_by_member,
                            global_config=config.global_config,
                        )
                    else:
                        raise
                rule_results.append(res)
                if res.is_evaluable:
                    evaluable_applicable_count += 1
            except Exception as exc:
                err = f"Error evaluating rule '{rule.rule_id}': {exc}"
                errors.append(err)
                rule_results.append(
                    RuleResult(
                        rule_id=rule.rule_id,
                        rule_type=rule.rule_type,
                        name=rule.name,
                        severity=rule.severity,
                        scope=rule.scope,
                        status=RuleResultStatus.ERROR,
                        explanation=err,
                        is_evaluable=False,
                    )
                )

        # 3. Compute data completeness (avoid divide-by-zero)
        if applicable_rules_count > 0:
            data_completeness = round(evaluable_applicable_count / applicable_rules_count, 3)
        else:
            data_completeness = None

        # 4. Determine overall team eligibility status based solely on HARD rules
        hard_failed: list[RuleResult] = []
        hard_needs_review: list[RuleResult] = []
        hard_passed: list[RuleResult] = []

        for r_res in rule_results:
            if r_res.severity == RuleSeverity.HARD:
                if r_res.status == RuleResultStatus.FAILED or r_res.status == RuleResultStatus.ERROR:
                    hard_failed.append(r_res)
                elif r_res.status == RuleResultStatus.NEEDS_REVIEW:
                    hard_needs_review.append(r_res)
                elif r_res.status == RuleResultStatus.PASSED:
                    hard_passed.append(r_res)

        reasons: list[str] = []
        if hard_failed:
            team_status = EligibilityStatus.INELIGIBLE
            ineligible_count += 1
            reasons = [r.explanation for r in hard_failed]
        elif hard_needs_review:
            team_status = EligibilityStatus.NEEDS_REVIEW
            needs_review_count += 1
            reasons = [r.explanation for r in hard_needs_review]
        else:
            team_status = EligibilityStatus.ELIGIBLE
            eligible_count += 1
            reasons = ["All hard eligibility criteria satisfied."]

        team_results.append(
            TeamEligibilityResult(
                team_id=team_obj.team_id,
                team_name=team_obj.team_name,
                status=team_status,
                reasons=reasons,
                rule_results=rule_results,
                data_completeness=data_completeness,
                is_temporary_id=getattr(team_obj, "is_temporary_id", False),
                is_unresolved=getattr(team_obj, "is_unresolved", False),
            )
        )

    # 5. Deterministic sorting by team_id
    team_results.sort(key=lambda t: str(t.team_id))

    summary = EligibilityRunSummary(
        total_teams=len(teams),
        eligible_count=eligible_count,
        ineligible_count=ineligible_count,
        needs_review_count=needs_review_count,
        error_count=error_count,
    )

    return EligibilityRunResponse(
        run_id=final_run_id,
        config_id=config.config_id,
        config_version=config.version,
        evaluated_at=now_ts,
        teams=team_results,
        summary=summary,
        warnings=warnings,
        errors=errors,
    )
