"""Cross-team rule evaluator for duplicate member emails across different teams."""

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


class DuplicateMemberEmailEvaluator(RuleEvaluatorBase):
    """Evaluates whether any member of the team is registered in another team with the same email."""

    @property
    def rule_type(self) -> str:
        return "duplicate_member_email"

    def evaluate(
        self,
        rule: RuleDefinition,
        team: TeamSchema,
        signals_by_member: dict[str, dict[str, ExtractedSignal]],
        global_config: GlobalRuleConfig,
        all_teams: Optional[list[TeamSchema]] = None,
    ) -> RuleResult:
        email_field = rule.parameters.get("email_field", "email")
        team_pool = all_teams or [team]

        # 1. Build global mapping: normalized_email -> dict of {team_id: [member_names]}
        email_to_teams: dict[str, dict[str, list[str]]] = {}

        for t in team_pool:
            if not t.members:
                continue
            for m in t.members:
                val, state = self.resolve_field(m, email_field)
                if state == "present" and val is not None:
                    norm = str(val).strip().lower()
                    if norm:  # Blank emails never count as duplicates
                        email_to_teams.setdefault(norm, {}).setdefault(t.team_id, []).append(m.name)

        # 2. Check current team's members for cross-team conflicts
        conflicts: list[str] = []
        conflicting_teams_set: set[str] = set()

        if team.members:
            for m in team.members:
                val, state = self.resolve_field(m, email_field)
                if state == "present" and val is not None:
                    norm = str(val).strip().lower()
                    if norm and norm in email_to_teams:
                        teams_with_email = email_to_teams[norm]
                        # Exclude current team (same-team repeats are ignored)
                        other_teams = sorted(t_id for t_id in teams_with_email.keys() if t_id != team.team_id)
                        if other_teams:
                            conflicting_teams_set.update(other_teams)
                            conflicts.append(f"'{m.name}' ({norm}) also in team(s): {', '.join(other_teams)}")

        if conflicts:
            conflicts_sorted = sorted(conflicts)
            explanation = (
                f"{rule.name}: Duplicate member email detected across teams. "
                + "; ".join(conflicts_sorted)
                + "."
            )
            return RuleResult(
                rule_id=rule.rule_id,
                rule_type=self.rule_type,
                name=rule.name,
                severity=rule.severity,
                scope=rule.scope,
                status=RuleResultStatus.FAILED,
                explanation=explanation,
                is_evaluable=True,
                details={
                    "conflicts": conflicts_sorted,
                    "conflicting_team_ids": sorted(conflicting_teams_set),
                },
            )
        else:
            return RuleResult(
                rule_id=rule.rule_id,
                rule_type=self.rule_type,
                name=rule.name,
                severity=rule.severity,
                scope=rule.scope,
                status=RuleResultStatus.PASSED,
                explanation=f"{rule.name}: No duplicate member emails detected across teams.",
                is_evaluable=True,
                details={"conflicting_team_ids": []},
            )
