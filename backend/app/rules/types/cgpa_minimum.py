"""Rule evaluator for minimum CGPA / CPI requirement."""

from __future__ import annotations

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


class CgpaMinimumEvaluator(RuleEvaluatorBase):
    """Evaluates whether candidates satisfy a minimum recorded CGPA / CPI threshold."""

    @property
    def rule_type(self) -> str:
        return "cgpa_minimum"

    def evaluate(
        self,
        rule: RuleDefinition,
        team: TeamSchema,
        signals_by_member: dict[str, dict[str, ExtractedSignal]],
        global_config: GlobalRuleConfig,
    ) -> RuleResult:
        min_cgpa = float(rule.parameters.get("min_cgpa", 6.0))
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
                details={"min_cgpa": min_cgpa},
            )

        evaluations: list[dict[str, Any]] = []

        for member in target_members:
            sig, state = self.resolve_signal(signals_by_member, member.member_id, "academic_cgpa")

            if state == "present" and sig and sig.value is not None:
                numeric_val, is_valid = self.parse_numeric(sig.value)
                if not is_valid or numeric_val is None:
                    # Invalid numeric (bool, NaN, Inf)
                    evaluations.append({
                        "member_id": member.member_id,
                        "name": member.name,
                        "status": "UNAVAILABLE",
                        "reason": f"Non-numeric or invalid CGPA value: {repr(sig.value)}",
                        "is_evaluable": False,
                    })
                elif numeric_val >= min_cgpa:
                    evaluations.append({
                        "member_id": member.member_id,
                        "name": member.name,
                        "status": "PASSED",
                        "reason": f"CGPA {numeric_val:.2f} >= minimum {min_cgpa:.2f}",
                        "is_evaluable": True,
                        "value": numeric_val,
                    })
                else:
                    evaluations.append({
                        "member_id": member.member_id,
                        "name": member.name,
                        "status": "FAILED",
                        "reason": f"CGPA {numeric_val:.2f} < minimum {min_cgpa:.2f}",
                        "is_evaluable": True,
                        "value": numeric_val,
                    })

            elif state == "not_provided":
                # Candidate did not provide CGPA in registration
                evaluations.append({
                    "member_id": member.member_id,
                    "name": member.name,
                    "status": "FAILED",
                    "reason": "CGPA was not provided in registration",
                    "is_evaluable": True,
                })
            else:
                # Signals payload absent or extraction failed/pending
                evaluations.append({
                    "member_id": member.member_id,
                    "name": member.name,
                    "status": "UNAVAILABLE",
                    "reason": "Academic CGPA signal unavailable",
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
            details={"min_cgpa": min_cgpa},
            member_evaluations=evaluations,
        )
