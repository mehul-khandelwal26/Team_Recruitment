"""Rule evaluator for team size range constraint."""

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


class TeamSizeRangeEvaluator(RuleEvaluatorBase):
    """Evaluates whether team member count is within the specified [min_size, max_size] range."""

    @property
    def rule_type(self) -> str:
        return "team_size_range"

    def evaluate(
        self,
        rule: RuleDefinition,
        team: TeamSchema,
        signals_by_member: dict[str, dict[str, ExtractedSignal]],
        global_config: GlobalRuleConfig,
    ) -> RuleResult:
        min_size = int(rule.parameters.get("min_size", 1))
        max_size = rule.parameters.get("max_size")
        if max_size is not None:
            max_size = int(max_size)

        actual_size = len(team.members)

        details: dict[str, Any] = {
            "actual_size": actual_size,
            "min_size": min_size,
            "max_size": max_size,
        }

        # Zero members is always an invalid structural team
        if actual_size == 0:
            return RuleResult(
                rule_id=rule.rule_id,
                rule_type=self.rule_type,
                name=rule.name,
                severity=rule.severity,
                scope=RuleScope.TEAM_LEVEL,
                status=RuleResultStatus.FAILED,
                explanation=f"{rule.name}: Team '{team.team_name}' has 0 members.",
                is_evaluable=True,
                details=details,
            )

        if actual_size < min_size:
            range_str = f"{min_size}+" if max_size is None else f"{min_size} to {max_size}"
            return RuleResult(
                rule_id=rule.rule_id,
                rule_type=self.rule_type,
                name=rule.name,
                severity=rule.severity,
                scope=RuleScope.TEAM_LEVEL,
                status=RuleResultStatus.FAILED,
                explanation=(
                    f"{rule.name}: Team has {actual_size} member(s), which is fewer than "
                    f"the required minimum of {min_size} (required: {range_str})."
                ),
                is_evaluable=True,
                details=details,
            )

        if max_size is not None and actual_size > max_size:
            return RuleResult(
                rule_id=rule.rule_id,
                rule_type=self.rule_type,
                name=rule.name,
                severity=rule.severity,
                scope=RuleScope.TEAM_LEVEL,
                status=RuleResultStatus.FAILED,
                explanation=(
                    f"{rule.name}: Team has {actual_size} member(s), which exceeds "
                    f"the maximum allowed limit of {max_size}."
                ),
                is_evaluable=True,
                details=details,
            )

        range_str = f"{min_size}+" if max_size is None else f"{min_size}-{max_size}"
        return RuleResult(
            rule_id=rule.rule_id,
            rule_type=self.rule_type,
            name=rule.name,
            severity=rule.severity,
            scope=RuleScope.TEAM_LEVEL,
            status=RuleResultStatus.PASSED,
            explanation=f"{rule.name}: Team size of {actual_size} meets the requirement ({range_str}).",
            is_evaluable=True,
            details=details,
        )
