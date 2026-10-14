"""Rule evaluator for required evaluation signal presence."""

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


class RequiredSignalPresentEvaluator(RuleEvaluatorBase):
    """Evaluates whether an evaluation signal has been successfully extracted."""

    @property
    def rule_type(self) -> str:
        return "required_signal_present"

    def evaluate(
        self,
        rule: RuleDefinition,
        team: TeamSchema,
        signals_by_member: dict[str, dict[str, ExtractedSignal]],
        global_config: GlobalRuleConfig,
        all_teams: Optional[list[TeamSchema]] = None,
    ) -> RuleResult:
        signal_key = rule.parameters.get("signal_key", "github_public_repo_count")
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
                details={"signal_key": signal_key},
            )

        evaluations: list[dict[str, Any]] = []

        for member in target_members:
            sig, state = self.resolve_signal(signals_by_member, member.member_id, signal_key)

            if state == "present":
                evaluations.append({
                    "member_id": member.member_id,
                    "name": member.name,
                    "status": "PASSED",
                    "reason": f"Signal '{signal_key}' is successfully extracted",
                    "is_evaluable": True,
                })
            elif state == "not_provided":
                # NOT_APPLICABLE: candidate did not provide input required for this signal
                evaluations.append({
                    "member_id": member.member_id,
                    "name": member.name,
                    "status": "FAILED",
                    "reason": f"Signal '{signal_key}' was not provided (input missing)",
                    "is_evaluable": True,
                })
            else:
                # FAILED, PENDING, or signal not supplied in payload
                evaluations.append({
                    "member_id": member.member_id,
                    "name": member.name,
                    "status": "UNAVAILABLE",
                    "reason": f"Signal '{signal_key}' is unavailable (extraction failed or not run)",
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
            details={"signal_key": signal_key},
            member_evaluations=evaluations,
        )
