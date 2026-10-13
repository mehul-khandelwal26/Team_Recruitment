"""Rule evaluator for allowed academic year / batch."""

from __future__ import annotations

import re
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


class AcademicYearRangeEvaluator(RuleEvaluatorBase):
    """Evaluates whether candidate's academic standing matches allowed years/batches."""

    @property
    def rule_type(self) -> str:
        return "academic_year_range"

    def evaluate(
        self,
        rule: RuleDefinition,
        team: TeamSchema,
        signals_by_member: dict[str, dict[str, ExtractedSignal]],
        global_config: GlobalRuleConfig,
    ) -> RuleResult:
        allowed = rule.parameters.get("allowed_years", ["2nd Year", "3rd Year", "4th Year"])
        normalized_allowed = [str(a).strip().lower() for a in allowed]

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
                details={"allowed_years": allowed},
            )

        evaluations: list[dict[str, Any]] = []

        for member in target_members:
            sig, state = self.resolve_signal(signals_by_member, member.member_id, "academic_year")

            if state == "present" and sig and sig.value is not None:
                val_str = str(sig.value).strip().lower()

                # Check exact match, ordinal match, or numeric match
                matches = False
                for a in normalized_allowed:
                    if a == val_str or a in val_str:
                        matches = True
                        break
                    # Numeric extraction check e.g. "3" in "3rd year"
                    digits_a = re.findall(r"\d+", a)
                    digits_val = re.findall(r"\d+", val_str)
                    if digits_a and digits_val and digits_a[0] == digits_val[0]:
                        matches = True
                        break

                if matches:
                    evaluations.append({
                        "member_id": member.member_id,
                        "name": member.name,
                        "status": "PASSED",
                        "reason": f"Academic year '{sig.value}' is allowed",
                        "is_evaluable": True,
                        "value": str(sig.value),
                    })
                else:
                    evaluations.append({
                        "member_id": member.member_id,
                        "name": member.name,
                        "status": "FAILED",
                        "reason": f"Academic year '{sig.value}' is not in allowed set {allowed}",
                        "is_evaluable": True,
                        "value": str(sig.value),
                    })

            elif state == "not_provided":
                evaluations.append({
                    "member_id": member.member_id,
                    "name": member.name,
                    "status": "FAILED",
                    "reason": "Academic year was not provided in registration",
                    "is_evaluable": True,
                })
            else:
                evaluations.append({
                    "member_id": member.member_id,
                    "name": member.name,
                    "status": "UNAVAILABLE",
                    "reason": "Academic year signal unavailable",
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
            details={"allowed_years": allowed},
            member_evaluations=evaluations,
        )
