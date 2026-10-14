"""Generic rule evaluator for numeric signal threshold comparisons with configurable aggregation."""

from __future__ import annotations

import operator
from typing import Any, Optional

from app.rules.schemas import (
    GlobalRuleConfig,
    RuleDefinition,
    RuleResult,
    RuleResultStatus,
    RuleScope,
)
from app.rules.types.base import RuleEvaluatorBase
from app.schemas.ingestion import TeamSchema
from app.signals.schemas import ExtractedSignal

_OPS = {
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
    "==": operator.eq,
    "!=": operator.ne,
    "=": operator.eq,
}


class SignalThresholdEvaluator(RuleEvaluatorBase):
    """Evaluates whether an arbitrary numeric signal meets a comparison threshold across team members."""

    @property
    def rule_type(self) -> str:
        return "signal_threshold"

    def evaluate(
        self,
        rule: RuleDefinition,
        team: TeamSchema,
        signals_by_member: dict[str, dict[str, ExtractedSignal]],
        global_config: GlobalRuleConfig,
        all_teams: Optional[list[TeamSchema]] = None,
    ) -> RuleResult:
        params = rule.parameters
        signal_key = params.get("signal_key")
        if not signal_key:
            return RuleResult(
                rule_id=rule.rule_id,
                rule_type=self.rule_type,
                name=rule.name,
                severity=rule.severity,
                scope=rule.scope,
                status=RuleResultStatus.ERROR,
                explanation=f"{rule.name}: Missing required parameter 'signal_key'.",
                is_evaluable=False,
            )

        op_str = params.get("operator", ">=")
        if op_str not in _OPS:
            return RuleResult(
                rule_id=rule.rule_id,
                rule_type=self.rule_type,
                name=rule.name,
                severity=rule.severity,
                scope=rule.scope,
                status=RuleResultStatus.ERROR,
                explanation=f"{rule.name}: Unsupported operator '{op_str}'.",
                is_evaluable=False,
            )
        compare_fn = _OPS[op_str]

        threshold_raw = params.get("threshold", 0.0)
        threshold_val, is_valid_thresh = self.parse_numeric(threshold_raw)
        if not is_valid_thresh or threshold_val is None:
            return RuleResult(
                rule_id=rule.rule_id,
                rule_type=self.rule_type,
                name=rule.name,
                severity=rule.severity,
                scope=rule.scope,
                status=RuleResultStatus.ERROR,
                explanation=f"{rule.name}: Invalid threshold '{threshold_raw}'.",
                is_evaluable=False,
            )

        # Member selection (parameter or field or scope)
        sel = rule.member_selection.value if rule.member_selection else params.get("member_selection")
        if not sel:
            if hasattr(rule.scope, "value"):
                sel = rule.scope.value
            else:
                sel = str(rule.scope)

        target_members, lead_error = self.resolve_scope_members(rule.scope, team, global_config, member_selection=sel)
        if lead_error:
            status = self.map_on_missing_to_status(rule.on_missing)
            return RuleResult(
                rule_id=rule.rule_id,
                rule_type=self.rule_type,
                name=rule.name,
                severity=rule.severity,
                scope=rule.scope,
                status=status,
                explanation=f"{rule.name}: {lead_error} Action taken: {self.on_missing_str(rule)}.",
                is_evaluable=False,
                details={"signal_key": signal_key, "member_selection": sel},
            )

        if not target_members:
            status = self.map_on_missing_to_status(rule.on_missing)
            return RuleResult(
                rule_id=rule.rule_id,
                rule_type=self.rule_type,
                name=rule.name,
                severity=rule.severity,
                scope=rule.scope,
                status=status,
                explanation=f"{rule.name}: Team '{team.team_name}' has no selected members for evaluation. Action taken: {self.on_missing_str(rule)}.",
                is_evaluable=False,
                details={"signal_key": signal_key, "member_selection": sel},
            )

        # Aggregation strategy: all, any, min, max, mean
        agg = rule.aggregation.value if rule.aggregation else params.get("aggregation", "all")
        if agg not in ("all", "any", "min", "max", "mean"):
            agg = "all"

        evaluations: list[dict[str, Any]] = []
        valid_numeric_values: list[float] = []

        for member in target_members:
            sig, state = self.resolve_signal(signals_by_member, member.member_id, signal_key)

            if state == "unavailable":
                evaluations.append({
                    "member_id": member.member_id,
                    "name": member.name,
                    "status": "UNAVAILABLE",
                    "reason": f"Signal '{signal_key}' is unavailable (extraction failed, skipped, or missing payload)",
                    "is_evaluable": False,
                    "value": None,
                })
            elif state == "not_provided":
                evaluations.append({
                    "member_id": member.member_id,
                    "name": member.name,
                    "status": "FAILED",
                    "reason": f"Signal '{signal_key}' was not provided (NOT_APPLICABLE)",
                    "is_evaluable": True,
                    "value": None,
                })
            else:
                # state == "present"
                num_val, is_valid = self.parse_numeric(sig.value)
                if not is_valid or num_val is None:
                    evaluations.append({
                        "member_id": member.member_id,
                        "name": member.name,
                        "status": "UNAVAILABLE",
                        "reason": f"Signal '{signal_key}' value {repr(sig.value)} is not a valid finite number",
                        "is_evaluable": False,
                        "value": sig.value,
                    })
                else:
                    valid_numeric_values.append(num_val)
                    passes = compare_fn(num_val, threshold_val)
                    evaluations.append({
                        "member_id": member.member_id,
                        "name": member.name,
                        "status": "PASSED" if passes else "FAILED",
                        "reason": f"{num_val} {op_str} {threshold_val} ({'satisfied' if passes else 'failed'})",
                        "is_evaluable": True,
                        "value": num_val,
                    })

        passed_evals = [e for e in evaluations if e["status"] == "PASSED"]
        failed_evals = [e for e in evaluations if e["status"] == "FAILED"]
        unavail_evals = [e for e in evaluations if e["status"] == "UNAVAILABLE"]

        # 1. Aggregation == "all": Logical AND across members
        if agg == "all":
            if failed_evals:
                names = ", ".join(f"{m['name']} ({m['reason']})" for m in failed_evals)
                return RuleResult(
                    rule_id=rule.rule_id,
                    rule_type=self.rule_type,
                    name=rule.name,
                    severity=rule.severity,
                    scope=rule.scope,
                    status=RuleResultStatus.FAILED,
                    explanation=f"{rule.name} failed for: {names}",
                    is_evaluable=True,
                    details={"signal_key": signal_key, "aggregation": agg, "operator": op_str, "threshold": threshold_val},
                    member_evaluations=evaluations,
                )
            if unavail_evals:
                status = self.map_on_missing_to_status(rule.on_missing)
                names = ", ".join(m["name"] for m in unavail_evals)
                return RuleResult(
                    rule_id=rule.rule_id,
                    rule_type=self.rule_type,
                    name=rule.name,
                    severity=rule.severity,
                    scope=rule.scope,
                    status=status,
                    explanation=f"{rule.name} data unavailable for: {names}. Action taken: {self.on_missing_str(rule)}.",
                    is_evaluable=False,
                    details={"signal_key": signal_key, "aggregation": agg, "operator": op_str, "threshold": threshold_val},
                    member_evaluations=evaluations,
                )
            return RuleResult(
                rule_id=rule.rule_id,
                rule_type=self.rule_type,
                name=rule.name,
                severity=rule.severity,
                scope=rule.scope,
                status=RuleResultStatus.PASSED,
                explanation=f"{rule.name} passed for all {len(evaluations)} selected member(s) ({op_str} {threshold_val}).",
                is_evaluable=True,
                details={"signal_key": signal_key, "aggregation": agg, "operator": op_str, "threshold": threshold_val},
                member_evaluations=evaluations,
            )

        # 2. Aggregation == "any": Logical OR across members
        elif agg == "any":
            if passed_evals:
                names = ", ".join(m["name"] for m in passed_evals)
                return RuleResult(
                    rule_id=rule.rule_id,
                    rule_type=self.rule_type,
                    name=rule.name,
                    severity=rule.severity,
                    scope=rule.scope,
                    status=RuleResultStatus.PASSED,
                    explanation=f"{rule.name} satisfied by: {names} ({op_str} {threshold_val}).",
                    is_evaluable=True,
                    details={"signal_key": signal_key, "aggregation": agg, "operator": op_str, "threshold": threshold_val},
                    member_evaluations=evaluations,
                )
            if unavail_evals:
                status = self.map_on_missing_to_status(rule.on_missing)
                names = ", ".join(m["name"] for m in unavail_evals)
                return RuleResult(
                    rule_id=rule.rule_id,
                    rule_type=self.rule_type,
                    name=rule.name,
                    severity=rule.severity,
                    scope=rule.scope,
                    status=status,
                    explanation=f"{rule.name} not satisfied and data unavailable for: {names}. Action taken: {self.on_missing_str(rule)}.",
                    is_evaluable=False,
                    details={"signal_key": signal_key, "aggregation": agg, "operator": op_str, "threshold": threshold_val},
                    member_evaluations=evaluations,
                )
            names = ", ".join(f"{m['name']} ({m['reason']})" for m in failed_evals)
            return RuleResult(
                rule_id=rule.rule_id,
                rule_type=self.rule_type,
                name=rule.name,
                severity=rule.severity,
                scope=rule.scope,
                status=RuleResultStatus.FAILED,
                explanation=f"{rule.name} failed for all selected members: {names}",
                is_evaluable=True,
                details={"signal_key": signal_key, "aggregation": agg, "operator": op_str, "threshold": threshold_val},
                member_evaluations=evaluations,
            )

        # 3. Numeric Reductions: min, max, mean
        else:
            # Rule C1: A member with a missing or unavailable signal value must never be silently dropped
            if unavail_evals or len(valid_numeric_values) < len(target_members):
                status = self.map_on_missing_to_status(rule.on_missing)
                missing_count = len(target_members) - len(valid_numeric_values)
                return RuleResult(
                    rule_id=rule.rule_id,
                    rule_type=self.rule_type,
                    name=rule.name,
                    severity=rule.severity,
                    scope=rule.scope,
                    status=status,
                    explanation=f"{rule.name}: Cannot reliably compute '{agg}' aggregation because {missing_count} member(s) have missing or unavailable data. Action taken: {self.on_missing_str(rule)}.",
                    is_evaluable=False,
                    details={"signal_key": signal_key, "aggregation": agg, "valid_count": len(valid_numeric_values), "target_count": len(target_members)},
                    member_evaluations=evaluations,
                )

            # All members have valid numeric values
            if agg == "min":
                aggregate_value = min(valid_numeric_values)
            elif agg == "max":
                aggregate_value = max(valid_numeric_values)
            elif agg == "mean":
                aggregate_value = sum(valid_numeric_values) / len(valid_numeric_values)
            else:
                aggregate_value = min(valid_numeric_values)

            passes = compare_fn(aggregate_value, threshold_val)
            res_status = RuleResultStatus.PASSED if passes else RuleResultStatus.FAILED
            outcome_str = "satisfied" if passes else "failed"

            return RuleResult(
                rule_id=rule.rule_id,
                rule_type=self.rule_type,
                name=rule.name,
                severity=rule.severity,
                scope=rule.scope,
                status=res_status,
                explanation=f"{rule.name}: Team {agg} value {aggregate_value:.2f} {op_str} {threshold_val} ({outcome_str}).",
                is_evaluable=True,
                details={"signal_key": signal_key, "aggregation": agg, "aggregate_value": aggregate_value, "operator": op_str, "threshold": threshold_val},
                member_evaluations=evaluations,
            )
