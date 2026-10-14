"""Rule evaluator for maximum team size constraint."""

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


class TeamSizeMaxEvaluator(RuleEvaluatorBase):
    """Evaluates whether team member count does not exceed max_size."""

    @property
    def rule_type(self) -> str:
        return "team_size_max"

    def evaluate(
        self,
        rule: RuleDefinition,
        team: TeamSchema,
        signals_by_member: dict[str, dict[str, ExtractedSignal]],
        global_config: GlobalRuleConfig,
        all_teams: Optional[list[TeamSchema]] = None,
    ) -> RuleResult:
        max_size_raw = rule.parameters.get("max_size")
        if max_size_raw is None:
            return RuleResult(
                rule_id=rule.rule_id,
                rule_type=self.rule_type,
                name=rule.name,
                severity=rule.severity,
                scope=rule.scope,
                status=RuleResultStatus.ERROR,
                explanation=f"{rule.name}: Missing required parameter 'max_size'.",
                is_evaluable=False,
            )

        try:
            max_size = int(max_size_raw)
        except (ValueError, TypeError):
            return RuleResult(
                rule_id=rule.rule_id,
                rule_type=self.rule_type,
                name=rule.name,
                severity=rule.severity,
                scope=rule.scope,
                status=RuleResultStatus.ERROR,
                explanation=f"{rule.name}: Invalid max_size parameter '{max_size_raw}'.",
                is_evaluable=False,
            )

        actual_size = len(team.members) if team.members else 0
        details: dict[str, Any] = {
            "actual_size": actual_size,
            "max_size": max_size,
        }

        if actual_size <= max_size:
            return RuleResult(
                rule_id=rule.rule_id,
                rule_type=self.rule_type,
                name=rule.name,
                severity=rule.severity,
                scope=rule.scope,
                status=RuleResultStatus.PASSED,
                explanation=f"{rule.name}: Team '{team.team_name}' has {actual_size} member(s), within maximum limit of {max_size}.",
                is_evaluable=True,
                details=details,
            )
        else:
            return RuleResult(
                rule_id=rule.rule_id,
                rule_type=self.rule_type,
                name=rule.name,
                severity=rule.severity,
                scope=rule.scope,
                status=RuleResultStatus.FAILED,
                explanation=f"{rule.name}: Team '{team.team_name}' has {actual_size} member(s), exceeding maximum limit of {max_size}.",
                is_evaluable=True,
                details=details,
            )
