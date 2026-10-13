"""Rule evaluator for minimum public GitHub repository count."""

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


class GithubReposMinimumEvaluator(RuleEvaluatorBase):
    """Evaluates whether candidates have at least the minimum public GitHub repositories."""

    @property
    def rule_type(self) -> str:
        return "github_repos_minimum"

    def evaluate(
        self,
        rule: RuleDefinition,
        team: TeamSchema,
        signals_by_member: dict[str, dict[str, ExtractedSignal]],
        global_config: GlobalRuleConfig,
    ) -> RuleResult:
        min_repos = int(rule.parameters.get("min_repos", 1))
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
                details={"min_repos": min_repos},
            )

        evaluations: list[dict[str, Any]] = []

        for member in target_members:
            sig, state = self.resolve_signal(signals_by_member, member.member_id, "github_public_repo_count")

            if state == "present" and sig and sig.value is not None:
                numeric_val, is_valid = self.parse_numeric(sig.value)
                if not is_valid or numeric_val is None:
                    evaluations.append({
                        "member_id": member.member_id,
                        "name": member.name,
                        "status": "UNAVAILABLE",
                        "reason": f"Non-numeric repo count: {repr(sig.value)}",
                        "is_evaluable": False,
                    })
                elif int(numeric_val) >= min_repos:
                    evaluations.append({
                        "member_id": member.member_id,
                        "name": member.name,
                        "status": "PASSED",
                        "reason": f"Public repos {int(numeric_val)} >= minimum {min_repos}",
                        "is_evaluable": True,
                        "value": int(numeric_val),
                    })
                else:
                    evaluations.append({
                        "member_id": member.member_id,
                        "name": member.name,
                        "status": "FAILED",
                        "reason": f"Public repos {int(numeric_val)} < minimum {min_repos}",
                        "is_evaluable": True,
                        "value": int(numeric_val),
                    })

            elif state == "not_provided":
                # Candidate did not provide GitHub profile
                evaluations.append({
                    "member_id": member.member_id,
                    "name": member.name,
                    "status": "FAILED",
                    "reason": "GitHub profile was not provided",
                    "is_evaluable": True,
                })
            else:
                # API error, rate limit, or signals not run
                evaluations.append({
                    "member_id": member.member_id,
                    "name": member.name,
                    "status": "UNAVAILABLE",
                    "reason": "GitHub repos signal unavailable (API error, rate limit, or not run)",
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
            details={"min_repos": min_repos},
            member_evaluations=evaluations,
        )
