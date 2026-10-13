"""Rule evaluator for custom signal numeric thresholds with strict numeric safety."""

from __future__ import annotations

import operator
from typing import Any

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

_OPERATORS = {
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
    "==": operator.eq,
    "=": operator.eq,
}


class CustomSignalThresholdEvaluator(RuleEvaluatorBase):
    """Evaluates whether an arbitrary numeric signal meets a specified comparison threshold.

    Enforces strict numeric safety:
    - Rejects booleans, NaN, and infinity as UNAVAILABLE.
    - Zero (0, 0.0) is a valid numeric value.
    """

    @property
    def rule_type(self) -> str:
        return "custom_signal_threshold"

    def evaluate(
        self,
        rule: RuleDefinition,
        team: TeamSchema,
        signals_by_member: dict[str, dict[str, ExtractedSignal]],
        global_config: GlobalRuleConfig,
    ) -> RuleResult:
        signal_key = rule.parameters.get("signal_key")
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

        threshold_val, is_thresh_valid = self.parse_numeric(rule.parameters.get("threshold", 0))
        if not is_thresh_valid or threshold_val is None:
            return RuleResult(
                rule_id=rule.rule_id,
                rule_type=self.rule_type,
                name=rule.name,
                severity=rule.severity,
                scope=rule.scope,
                status=RuleResultStatus.ERROR,
                explanation=f"{rule.name}: Invalid comparison threshold {repr(rule.parameters.get('threshold'))}.",
                is_evaluable=False,
            )

        op_str = rule.parameters.get("operator", ">=")
        op_func = _OPERATORS.get(op_str, operator.ge)

        target_members, lead_error = self.resolve_scope_members(rule.scope, team, global_config)

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
                details={"signal_key": signal_key, "threshold": threshold_val},
            )

        evaluations: list[dict[str, Any]] = []

        for member in target_members:
            sig, state = self.resolve_signal(signals_by_member, member.member_id, signal_key)

            if state == "present" and sig and sig.value is not None:
                numeric_val, is_valid = self.parse_numeric(sig.value)

                # Strict numeric safety: reject booleans, NaN, and Inf as invalid data
                if not is_valid or numeric_val is None:
                    evaluations.append({
                        "member_id": member.member_id,
                        "name": member.name,
                        "status": "UNAVAILABLE",
                        "reason": f"Signal '{signal_key}' has non-numeric or invalid value: {repr(sig.value)}",
                        "is_evaluable": False,
                    })
                elif op_func(numeric_val, threshold_val):
                    evaluations.append({
                        "member_id": member.member_id,
                        "name": member.name,
                        "status": "PASSED",
                        "reason": f"Signal '{signal_key}' value {numeric_val} {op_str} {threshold_val}",
                        "is_evaluable": True,
                        "value": numeric_val,
                    })
                else:
                    evaluations.append({
                        "member_id": member.member_id,
                        "name": member.name,
                        "status": "FAILED",
                        "reason": f"Signal '{signal_key}' value {numeric_val} does not satisfy {op_str} {threshold_val}",
                        "is_evaluable": True,
                        "value": numeric_val,
                    })

            elif state == "not_provided":
                # Candidate did not provide input for this signal
                evaluations.append({
                    "member_id": member.member_id,
                    "name": member.name,
                    "status": "FAILED",
                    "reason": f"Signal '{signal_key}' input was not provided",
                    "is_evaluable": True,
                })
            else:
                # FAILED, PENDING, or absent from payload
                evaluations.append({
                    "member_id": member.member_id,
                    "name": member.name,
                    "status": "UNAVAILABLE",
                    "reason": f"Signal '{signal_key}' is unavailable",
                    "is_evaluable": False,
                })

        status, explanation, is_evaluable = self.aggregate_member_evaluations(rule, evaluations)

        return RuleResult(
            rule_id=rule.rule_id,
            rule_type=self.rule_type,
            name=rule.name,
            severity=rule.severity,
            scope=rule.scope,
            status=status,
            explanation=explanation,
            is_evaluable=is_evaluable,
            details={
                "signal_key": signal_key,
                "operator": op_str,
                "threshold": threshold_val,
            },
            member_evaluations=evaluations,
        )
