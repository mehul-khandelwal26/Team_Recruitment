"""Rule evaluator for track team capacity limits."""

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


def _resolve_team_track(team: TeamSchema, field_key: str) -> tuple[Optional[str], str]:
    """Resolve track identifier for a team from its members or raw attributes."""
    if not team.members:
        return None, "unmapped"

    # Check first member or team lead
    for member in team.members:
        val, state = RuleEvaluatorBase.resolve_field(member, field_key)
        if state == "present" and val is not None and str(val).strip():
            return str(val).strip(), "present"
        if state == "not_provided":
            return None, "not_provided"

    # Check unmapped
    return None, "unmapped"


class TrackLimitEvaluator(RuleEvaluatorBase):
    """Evaluates whether the number of teams registered for a given track exceeds the configured limit."""

    @property
    def rule_type(self) -> str:
        return "track_limit"

    def evaluate(
        self,
        rule: RuleDefinition,
        team: TeamSchema,
        signals_by_member: dict[str, dict[str, ExtractedSignal]],
        global_config: GlobalRuleConfig,
        all_teams: Optional[list[TeamSchema]] = None,
    ) -> RuleResult:
        params = rule.parameters
        field_key = params.get("field_key")
        if not field_key:
            return RuleResult(
                rule_id=rule.rule_id,
                rule_type=self.rule_type,
                name=rule.name,
                severity=rule.severity,
                scope=rule.scope,
                status=RuleResultStatus.ERROR,
                explanation=f"{rule.name}: Missing required parameter 'field_key'.",
                is_evaluable=False,
            )

        # Parse limits: either track_limits dict or track + limit
        limits_map: dict[str, int] = {}
        if "track_limits" in params and isinstance(params["track_limits"], dict):
            for k, v in params["track_limits"].items():
                try:
                    limits_map[str(k).strip().lower()] = int(v)
                except (ValueError, TypeError):
                    pass
        elif "limit" in params:
            try:
                lim = int(params["limit"])
                trk = params.get("track")
                if trk:
                    limits_map[str(trk).strip().lower()] = lim
                else:
                    # Global per-track limit
                    limits_map["__default__"] = lim
            except (ValueError, TypeError):
                pass

        if not limits_map:
            return RuleResult(
                rule_id=rule.rule_id,
                rule_type=self.rule_type,
                name=rule.name,
                severity=rule.severity,
                scope=rule.scope,
                status=RuleResultStatus.ERROR,
                explanation=f"{rule.name}: Missing or invalid track limits configuration.",
                is_evaluable=False,
            )

        # Resolve track for current team
        team_track, track_state = _resolve_team_track(team, field_key)

        if track_state == "unmapped" or not team_track:
            # Unmapped or absent track = UNAVAILABLE -> apply on_missing
            status = self.map_on_missing_to_status(rule.on_missing)
            return RuleResult(
                rule_id=rule.rule_id,
                rule_type=self.rule_type,
                name=rule.name,
                severity=rule.severity,
                scope=rule.scope,
                status=status,
                explanation=f"{rule.name}: Track field '{field_key}' is absent or unmapped for team '{team.team_name}'. Action taken: {self.on_missing_str(rule)}.",
                is_evaluable=False,
                details={"field_key": field_key, "team_track": None},
            )

        # Calculate track counts across submitted teams
        team_pool = all_teams or [team]
        track_counts: dict[str, int] = {}
        for t in team_pool:
            t_trk, t_st = _resolve_team_track(t, field_key)
            if t_st == "present" and t_trk:
                key_norm = t_trk.strip().lower()
                track_counts[key_norm] = track_counts.get(key_norm, 0) + 1

        norm_track = team_track.lower()
        limit = limits_map.get(norm_track) or limits_map.get("__default__")
        count = track_counts.get(norm_track, 1)

        if limit is None:
            # No limit configured for this specific track -> Passes
            return RuleResult(
                rule_id=rule.rule_id,
                rule_type=self.rule_type,
                name=rule.name,
                severity=rule.severity,
                scope=rule.scope,
                status=RuleResultStatus.PASSED,
                explanation=f"{rule.name}: Team '{team.team_name}' is in track '{team_track}' (no limit configured).",
                is_evaluable=True,
                details={"team_track": team_track, "count": count, "limit": None},
            )

        if count <= limit:
            return RuleResult(
                rule_id=rule.rule_id,
                rule_type=self.rule_type,
                name=rule.name,
                severity=rule.severity,
                scope=rule.scope,
                status=RuleResultStatus.PASSED,
                explanation=f"{rule.name}: Track '{team_track}' has {count} team(s), within limit of {limit}.",
                is_evaluable=True,
                details={"team_track": team_track, "count": count, "limit": limit},
            )
        else:
            return RuleResult(
                rule_id=rule.rule_id,
                rule_type=self.rule_type,
                name=rule.name,
                severity=rule.severity,
                scope=rule.scope,
                status=RuleResultStatus.FAILED,
                explanation=f"{rule.name}: Track '{team_track}' has {count} team(s), exceeding limit of {limit}.",
                is_evaluable=True,
                details={"team_track": team_track, "count": count, "limit": limit},
            )
