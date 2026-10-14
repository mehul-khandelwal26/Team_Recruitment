"""Rule evaluator for allowed values on custom or canonical fields (e.g. track, branch)."""

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


class AllowedValuesEvaluator(RuleEvaluatorBase):
    """Evaluates whether a designated field contains one of the permitted values.

    Field lookup order:
    1. member.custom_fields
    2. member.raw_data
    3. canonical MemberSchema attributes
    """

    @property
    def rule_type(self) -> str:
        return "allowed_values"

    def evaluate(
        self,
        rule: RuleDefinition,
        team: TeamSchema,
        signals_by_member: dict[str, dict[str, ExtractedSignal]],
        global_config: GlobalRuleConfig,
        all_teams: Optional[list[TeamSchema]] = None,
    ) -> RuleResult:
        field_key = rule.parameters.get("field_key")
        signal_key = rule.parameters.get("signal_key")
        if not field_key and not signal_key:
            return RuleResult(
                rule_id=rule.rule_id,
                rule_type=self.rule_type,
                name=rule.name,
                severity=rule.severity,
                scope=rule.scope,
                status=RuleResultStatus.ERROR,
                explanation=f"{rule.name}: Missing required parameter 'field_key' or 'signal_key' in rule definition.",
                is_evaluable=False,
            )

        allowed = rule.parameters.get("allowed_values", [])
        normalized_allowed = [str(x).strip().lower() for x in allowed]

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
                details={"field_key": field_key or signal_key, "allowed_values": allowed},
            )

        evaluations: list[dict[str, Any]] = []

        for member in target_members:
            if signal_key:
                sig, state = self.resolve_signal(signals_by_member, member.member_id, signal_key)
                val = sig.value if sig else None
            else:
                val, state = self.resolve_field(member, field_key)

            target_name = signal_key if signal_key else field_key

            if state == "present" and val is not None:
                val_str = str(val).strip().lower()
                if val_str in normalized_allowed:
                    evaluations.append({
                        "member_id": member.member_id,
                        "name": member.name,
                        "status": "PASSED",
                        "reason": f"Value '{val}' is permitted in {target_name}",
                        "is_evaluable": True,
                        "value": str(val),
                    })
                else:
                    evaluations.append({
                        "member_id": member.member_id,
                        "name": member.name,
                        "status": "FAILED",
                        "reason": f"Value '{val}' in {target_name} is not in allowed list {allowed}",
                        "is_evaluable": True,
                        "value": str(val),
                    })

            elif state == "not_provided":
                evaluations.append({
                    "member_id": member.member_id,
                    "name": member.name,
                    "status": "FAILED",
                    "reason": f"Field/signal '{target_name}' was not provided (blank or NOT_APPLICABLE)",
                    "is_evaluable": True,
                })
            else:
                evaluations.append({
                    "member_id": member.member_id,
                    "name": member.name,
                    "status": "UNAVAILABLE",
                    "reason": f"Field/signal '{target_name}' is unmapped or unavailable",
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
            details={"field_key": field_key, "allowed_values": allowed},
            member_evaluations=evaluations,
        )
