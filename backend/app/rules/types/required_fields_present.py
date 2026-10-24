"""Rule evaluator for required registration fields presence."""

from __future__ import annotations

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


class RequiredFieldsPresentEvaluator(RuleEvaluatorBase):
    """Evaluates whether all specified registration fields are populated."""

    @property
    def rule_type(self) -> str:
        return "required_fields_present"

    def evaluate(
        self,
        rule: RuleDefinition,
        team: TeamSchema,
        signals_by_member: dict[str, dict[str, ExtractedSignal]],
        global_config: GlobalRuleConfig,
        all_teams: Optional[list[TeamSchema]] = None,
    ) -> RuleResult:
        field_keys = rule.parameters.get("field_keys")
        if not field_keys and "field_key" in rule.parameters:
            field_keys = [rule.parameters["field_key"]]
        if not field_keys:
            field_keys = ["email"]

        sel = rule.member_selection.value if rule.member_selection else rule.parameters.get("member_selection")
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
                details={"required_fields": field_keys},
            )

        evaluations: list[dict[str, Any]] = []

        for member in target_members:
            missing_fields: list[str] = []
            unmapped_fields: list[str] = []

            for f_key in field_keys:
                val, state = self.resolve_field(member, f_key)
                if state == "not_provided":
                    missing_fields.append(f_key)
                elif state == "unmapped":
                    unmapped_fields.append(f_key)

            if unmapped_fields:
                evaluations.append({
                    "member_id": member.member_id,
                    "name": member.name,
                    "status": "UNAVAILABLE",
                    "reason": f"Required fields unmapped: {', '.join(unmapped_fields)}",
                    "is_evaluable": False,
                })
            elif missing_fields:
                evaluations.append({
                    "member_id": member.member_id,
                    "name": member.name,
                    "status": "FAILED",
                    "reason": f"Required fields missing: {', '.join(missing_fields)}",
                    "is_evaluable": True,
                })
            else:
                evaluations.append({
                    "member_id": member.member_id,
                    "name": member.name,
                    "status": "PASSED",
                    "reason": "All required fields populated",
                    "is_evaluable": True,
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
            details={"field_keys": field_keys},
            member_evaluations=evaluations,
        )
