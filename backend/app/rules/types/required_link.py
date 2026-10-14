"""Rule evaluator for required URL links (GitHub, LinkedIn, Portfolio, Resume)."""

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


class RequiredLinkEvaluator(RuleEvaluatorBase):
    """Evaluates whether candidates provide a required link/URL."""

    @property
    def rule_type(self) -> str:
        return "required_link"

    def evaluate(
        self,
        rule: RuleDefinition,
        team: TeamSchema,
        signals_by_member: dict[str, dict[str, ExtractedSignal]],
        global_config: GlobalRuleConfig,
        all_teams: Optional[list[TeamSchema]] = None,
    ) -> RuleResult:
        link_field = rule.parameters.get("link_field") or rule.parameters.get("link_type", "github_url")
        link_type = link_field
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
                details={"link_field": link_field, "scope": rule.scope.value},
            )

        evaluations: list[dict[str, Any]] = []

        for member in target_members:
            val, state = self.resolve_field(member, link_type)

            if state == "present" and val:
                evaluations.append({
                    "member_id": member.member_id,
                    "name": member.name,
                    "status": "PASSED",
                    "reason": f"Provided valid {link_type}",
                    "is_evaluable": True,
                    "value": str(val),
                })
            elif state == "not_provided":
                # Known/mapped field was empty
                evaluations.append({
                    "member_id": member.member_id,
                    "name": member.name,
                    "status": "FAILED",
                    "reason": f"Missing required {link_type} (not provided)",
                    "is_evaluable": True,
                    "value": None,
                })
            else:
                # Field unmapped / cannot be determined
                evaluations.append({
                    "member_id": member.member_id,
                    "name": member.name,
                    "status": "UNAVAILABLE",
                    "reason": f"Field '{link_type}' not mapped or not collected",
                    "is_evaluable": False,
                    "value": None,
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
            details={"link_type": link_type, "evaluations_count": len(evaluations)},
            member_evaluations=evaluations,
        )
