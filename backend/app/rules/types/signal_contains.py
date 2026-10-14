"""Rule evaluator for checking containment in list or dictionary signal structures."""

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


def _contains_case_insensitive(container: Any, target: str, dict_key: Optional[str] = None) -> bool:
    """Check whether container (list, dict, or nested structure) contains the target string."""
    target_clean = str(target).strip().lower()

    if isinstance(container, dict):
        if dict_key and dict_key in container:
            return _contains_case_insensitive(container[dict_key], target, dict_key=None)
        # Check dict keys
        for k in container.keys():
            if str(k).strip().lower() == target_clean:
                return True
        # Check dict values (including nested lists)
        for v in container.values():
            if _contains_case_insensitive(v, target, dict_key=None):
                return True
        return False

    if isinstance(container, (list, tuple, set)):
        for item in container:
            if isinstance(item, (list, tuple, set, dict)):
                if _contains_case_insensitive(item, target, dict_key=None):
                    return True
            elif str(item).strip().lower() == target_clean:
                return True
        return False

    if isinstance(container, str):
        return target_clean in container.strip().lower()

    return False


class SignalContainsEvaluator(RuleEvaluatorBase):
    """Evaluates whether a list or dictionary signal contains an expected value."""

    @property
    def rule_type(self) -> str:
        return "signal_contains"

    def evaluate(
        self,
        rule: RuleDefinition,
        team: TeamSchema,
        signals_by_member: dict[str, dict[str, ExtractedSignal]],
        global_config: GlobalRuleConfig,
        all_teams: Optional[list[TeamSchema]] = None,
    ) -> RuleResult:
        params = rule.parameters
        signal_key = params.get("signal_key")
        expected_value = params.get("expected_value")

        if not signal_key:
            return RuleResult(
                rule_id=rule.rule_id,
                rule_type=self.rule_type,
                name=rule.name,
                severity=rule.severity,
                scope=rule.scope,
                status=RuleResultStatus.ERROR,
                explanation=f"{rule.name}: Missing required parameter 'signal_key'.",
                is_evaluable=False,
            )

        if expected_value is None or (isinstance(expected_value, str) and not expected_value.strip()):
            return RuleResult(
                rule_id=rule.rule_id,
                rule_type=self.rule_type,
                name=rule.name,
                severity=rule.severity,
                scope=rule.scope,
                status=RuleResultStatus.ERROR,
                explanation=f"{rule.name}: Missing required parameter 'expected_value'.",
                is_evaluable=False,
            )

        dict_key = params.get("dict_key")
        sel = rule.member_selection.value if rule.member_selection else params.get("member_selection", "any_member")

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
                details={"signal_key": signal_key, "member_selection": sel},
            )

        evaluations: list[dict[str, Any]] = []

        for member in target_members:
            sig, state = self.resolve_signal(signals_by_member, member.member_id, signal_key)

            if state == "unavailable":
                evaluations.append({
                    "member_id": member.member_id,
                    "name": member.name,
                    "status": "UNAVAILABLE",
                    "reason": f"Signal '{signal_key}' is unavailable",
                    "is_evaluable": False,
                    "value": None,
                })
            elif state == "not_provided":
                evaluations.append({
                    "member_id": member.member_id,
                    "name": member.name,
                    "status": "FAILED",
                    "reason": f"Signal '{signal_key}' was not provided (NOT_APPLICABLE)",
                    "is_evaluable": True,
                    "value": None,
                })
            else:
                # Value present: inspect container structure
                val = sig.value
                if val is None or not isinstance(val, (list, tuple, set, dict, str)):
                    # Incompatible structure at runtime -> UNAVAILABLE
                    evaluations.append({
                        "member_id": member.member_id,
                        "name": member.name,
                        "status": "UNAVAILABLE",
                        "reason": f"Signal '{signal_key}' runtime value type {type(val).__name__} is incompatible with signal_contains",
                        "is_evaluable": False,
                        "value": val,
                    })
                else:
                    found = _contains_case_insensitive(val, str(expected_value), dict_key=dict_key)
                    evaluations.append({
                        "member_id": member.member_id,
                        "name": member.name,
                        "status": "PASSED" if found else "FAILED",
                        "reason": f"Contains '{expected_value}'" if found else f"Does not contain '{expected_value}'",
                        "is_evaluable": True,
                        "value": val,
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
            details={"signal_key": signal_key, "expected_value": expected_value, "dict_key": dict_key},
            member_evaluations=evaluations,
        )
