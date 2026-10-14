"""Base class and common helpers for all eligibility rule type evaluators.

Handles:
- Missing data semantics:
  * NOT PROVIDED = field/signal is known/expected and absent for this member (fails rule).
  * UNAVAILABLE = cannot be determined (unmapped, analyzer error, absent payload); triggers on_missing.
- Numeric safety:
  * Rejects bool (e.g. True/False), NaN, and infinity as invalid (UNAVAILABLE).
  * Validates and preserves zero (0, 0.0) as legitimate numeric data.
- Explicit field resolution order:
  * custom_fields -> raw_data -> canonical MemberSchema attributes.
- Scope resolution:
  * all_members, any_member, team_lead, team_level.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import Any, Optional

from app.rules.schemas import (
    GlobalRuleConfig,
    OnMissingAction,
    RuleDefinition,
    RuleResult,
    RuleResultStatus,
    RuleScope,
)
from app.schemas.ingestion import FieldPresenceStatus, KNOWN_MEMBER_FIELDS, MemberSchema, TeamSchema
from app.signals.schemas import ExtractedSignal, SignalStatus


class RuleEvaluatorBase(ABC):
    """Abstract base class for all eligibility rule evaluators."""

    @property
    @abstractmethod
    def rule_type(self) -> str:
        """The identifier string of this rule type."""
        raise NotImplementedError

    @abstractmethod
    def evaluate(
        self,
        rule: RuleDefinition,
        team: TeamSchema,
        signals_by_member: dict[str, dict[str, ExtractedSignal]],
        global_config: GlobalRuleConfig,
        all_teams: Optional[list[TeamSchema]] = None,
    ) -> RuleResult:
        """Evaluate the rule against the given team and signals."""
        raise NotImplementedError

    # -----------------------------------------------------------------------
    # Field & Data Resolution Helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def resolve_field(member: MemberSchema, field_key: str) -> tuple[Optional[Any], str]:
        """Resolve a field value according to explicit precedence:
        1. member.custom_fields
        2. member.raw_data
        3. canonical MemberSchema attribute

        Returns:
            (value, presence_state)
            presence_state is one of:
            - 'present': field exists with non-empty value
            - 'not_provided': field is known/mapped but was blank/null
            - 'unmapped': field was not mapped or not present in registration data
        """
        # 1. Check explicit field_statuses if available
        if field_key in member.field_statuses:
            status = member.field_statuses[field_key]
            if status == FieldPresenceStatus.NOT_COLLECTED:
                return None, "unmapped"
            if status == FieldPresenceStatus.COLLECTED_BLANK:
                return None, "not_provided"
            if status == FieldPresenceStatus.INVALID:
                return None, "not_provided"

        # Check custom_fields
        if field_key in member.custom_fields:
            val = member.custom_fields[field_key]
            if val is None or (isinstance(val, str) and not val.strip()):
                return None, "not_provided"
            return val, "present"

        # Check raw_data
        if field_key in member.raw_data:
            val = member.raw_data[field_key]
            if val is None or (isinstance(val, str) and not val.strip()):
                return None, "not_provided"
            return val, "present"

        # Check canonical attributes
        if field_key in KNOWN_MEMBER_FIELDS:
            val = getattr(member, field_key, None)
            if val is not None:
                if isinstance(val, str) and not val.strip():
                    return None, "not_provided"
                return val, "present"

            # If raw_data is populated and field_key was NOT in raw_data, it wasn't in input
            if member.raw_data and field_key not in member.raw_data:
                return None, "unmapped"
            return None, "not_provided"

        # Neither custom, raw, nor canonical
        return None, "unmapped"

    @staticmethod
    def resolve_signal(
        signals_by_member: dict[str, dict[str, ExtractedSignal]],
        member_id: str,
        signal_key: str,
    ) -> tuple[Optional[ExtractedSignal], str]:
        """Resolve signal from pre-extracted payload.

        Contradiction resolution semantics:
        - SignalStatus.NOT_APPLICABLE: NOT PROVIDED (member had no input for this signal; rule FAILS).
        - SignalStatus.EXTRACTED: PRESENT (usable extracted value).
        - SignalStatus.FAILED / PENDING / SKIPPED or payload absent: UNAVAILABLE (on_missing applies).

        Returns:
            (extracted_signal, state) where state is:
            - 'present': successfully extracted
            - 'not_provided': input missing (NOT_APPLICABLE)
            - 'unavailable': extraction error, pending, or payload absent
        """
        if not signals_by_member or member_id not in signals_by_member:
            return None, "unavailable"

        member_sigs = signals_by_member[member_id]
        if signal_key not in member_sigs:
            return None, "unavailable"

        sig = member_sigs[signal_key]
        if sig.status == SignalStatus.EXTRACTED:
            return sig, "present"
        if sig.status == SignalStatus.NOT_APPLICABLE:
            return sig, "not_provided"

        # FAILED, PENDING, SKIPPED
        return sig, "unavailable"

    @staticmethod
    def parse_numeric(val: Any) -> tuple[Optional[float], bool]:
        """Parse numeric value with strict type and domain safety.

        Rejects:
        - Booleans (bool is a subclass of int in Python; rejected as invalid)
        - NaN (math.isnan)
        - Infinity / -Infinity (math.isinf)
        - Non-numeric unparseable strings

        Accepts:
        - 0, 0.0 (Zero is explicitly valid and preserved)
        - Finite float/int numbers

        Returns:
            (float_value, is_valid)
        """
        if isinstance(val, bool):
            return None, False

        if isinstance(val, (int, float)):
            if math.isnan(val) or math.isinf(val):
                return None, False
            return float(val), True

        if isinstance(val, str):
            clean = val.strip()
            if not clean:
                return None, False
            try:
                num = float(clean)
                if math.isnan(num) or math.isinf(num):
                    return None, False
                return num, True
            except (ValueError, TypeError):
                return None, False

        return None, False

    @staticmethod
    def resolve_scope_members(
        scope: Any,
        team: TeamSchema,
        global_config: GlobalRuleConfig,
        member_selection: Any = None,
    ) -> tuple[list[MemberSchema], Optional[str]]:
        """Resolve target members based on rule scope or member_selection.

        Returns:
            (members_list, error_or_unresolved_reason)
            If error_or_unresolved_reason is not None, evaluation should be UNAVAILABLE.
        """
        sel = member_selection
        if sel is None:
            if hasattr(scope, "value"):
                sel = scope.value
            else:
                sel = str(scope)

        if sel in ("team_lead", RuleScope.TEAM_LEAD.value):
            lead_field = global_config.lead_field or "role"
            lead_values = [v.lower() for v in global_config.lead_values]

            for member in team.members:
                val, state = RuleEvaluatorBase.resolve_field(member, lead_field)
                if state == "present" and str(val).strip().lower() in lead_values:
                    return [member], None

            return [], f"Team lead could not be determined using lead field '{lead_field}'."

        return team.members, None

    @staticmethod
    def map_on_missing_to_status(on_missing: OnMissingAction) -> RuleResultStatus:
        """Map rule's on_missing setting to a RuleResultStatus."""
        if on_missing == OnMissingAction.MANUAL_REVIEW:
            return RuleResultStatus.NEEDS_REVIEW
        if on_missing == OnMissingAction.FAIL:
            return RuleResultStatus.FAILED
        if on_missing == OnMissingAction.PASS:
            return RuleResultStatus.PASSED
        if on_missing == OnMissingAction.SKIP:
            return RuleResultStatus.SKIPPED
        return RuleResultStatus.NEEDS_REVIEW

    @staticmethod
    def on_missing_str(rule: RuleDefinition) -> str:
        """Return human-readable string for on_missing action."""
        return rule.on_missing.value if hasattr(rule.on_missing, "value") else str(rule.on_missing)

    @staticmethod
    def aggregate_member_evaluations(
        rule: RuleDefinition,
        evaluations: list[dict[str, Any]],
    ) -> tuple[RuleResultStatus, str, bool]:
        """Aggregate per-member evaluation records into a unified rule status and explanation.

        Each evaluation dict contains:
        {
            "member_id": str,
            "name": str,
            "status": "PASSED" | "FAILED" | "UNAVAILABLE",
            "reason": str,
            "is_evaluable": bool
        }

        Returns:
            (status, explanation, is_evaluable)
        """
        if not evaluations:
            # e.g. empty members or lead not resolved
            status = RuleEvaluatorBase.map_on_missing_to_status(rule.on_missing)
            return status, f"{rule.name}: No members available for evaluation.", False

        passed_members = [e for e in evaluations if e["status"] == "PASSED"]
        failed_members = [e for e in evaluations if e["status"] == "FAILED"]
        unavail_members = [e for e in evaluations if e["status"] == "UNAVAILABLE"]

        all_evaluable = all(e.get("is_evaluable", True) for e in evaluations)

        # Determine effective selection mode
        sel = rule.member_selection.value if rule.member_selection else None
        if sel is None:
            if hasattr(rule.scope, "value"):
                sel = rule.scope.value
            else:
                sel = str(rule.scope)

        if sel in ("any_member", RuleScope.ANY_MEMBER.value):
            if passed_members:
                names = ", ".join(m["name"] for m in passed_members)
                return RuleResultStatus.PASSED, f"{rule.name} satisfied by: {names}.", True
            if unavail_members:
                status = RuleEvaluatorBase.map_on_missing_to_status(rule.on_missing)
                names = ", ".join(m["name"] for m in unavail_members)
                return status, f"{rule.name} not satisfied and data unavailable for: {names}.", False
            names = ", ".join(f"{m['name']} ({m['reason']})" for m in failed_members)
            return RuleResultStatus.FAILED, f"{rule.name} failed for all members: {names}", True

        elif sel in ("team_lead", RuleScope.TEAM_LEAD.value):
            lead_eval = evaluations[0]
            if lead_eval["status"] == "PASSED":
                return RuleResultStatus.PASSED, f"{rule.name} passed for team lead {lead_eval['name']}.", True
            if lead_eval["status"] == "FAILED":
                return RuleResultStatus.FAILED, f"{rule.name} failed for team lead {lead_eval['name']}: {lead_eval['reason']}.", True
            status = RuleEvaluatorBase.map_on_missing_to_status(rule.on_missing)
            return status, f"{rule.name} data unavailable for team lead {lead_eval['name']}.", False

        elif sel in ("all_members", RuleScope.ALL_MEMBERS.value, "member", RuleScope.MEMBER.value):
            if failed_members:
                names = ", ".join(f"{m['name']} ({m['reason']})" for m in failed_members)
                return RuleResultStatus.FAILED, f"{rule.name} failed for: {names}", all_evaluable
            if unavail_members:
                status = RuleEvaluatorBase.map_on_missing_to_status(rule.on_missing)
                names = ", ".join(m["name"] for m in unavail_members)
                action_str = rule.on_missing.value if hasattr(rule.on_missing, "value") else str(rule.on_missing)
                return status, f"{rule.name} data unavailable for: {names}. Action taken: {action_str}.", False
            return RuleResultStatus.PASSED, f"{rule.name} passed for all {len(evaluations)} members.", True

        # TEAM_LEVEL fallback
        if failed_members:
            return RuleResultStatus.FAILED, evaluations[0].get("reason", "Failed"), all_evaluable
        if unavail_members:
            status = RuleEvaluatorBase.map_on_missing_to_status(rule.on_missing)
            return status, evaluations[0].get("reason", "Data unavailable"), False
        return RuleResultStatus.PASSED, evaluations[0].get("reason", "Passed"), True
