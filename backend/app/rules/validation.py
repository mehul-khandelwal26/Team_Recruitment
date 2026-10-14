"""Configuration validation for eligibility rules (Prompt 4.1 Step E).

Validates rule configurations during creation and update, raising HTTP 422
with descriptive error messages for any validation failure:
- Unknown rule_type
- Unsupported operator for the selected rule type
- Wrong threshold type (e.g. booleans, non-numeric strings, NaN, infinity)
- Invalid on_missing
- Invalid severity
- Invalid scope
- Invalid aggregation
- Invalid member-selection value
- Missing required parameters or invalid parameter types
- Unknown signal key (validated against actual default_signal_registry)
- Signal value type incompatible with selected rule
- Incompatible track-limit, signal_contains, or allowed_values configuration
- Duplicate rule IDs within the same configuration
"""

from __future__ import annotations

import math
from typing import Any
from fastapi import HTTPException

from app.rules.schemas import (
    AggregationMethod,
    MemberSelection,
    OnMissingAction,
    RuleConfigurationCreate,
    RuleConfigurationUpdate,
    RuleDefinition,
    RuleScope,
    RuleSeverity,
)
from app.rules.types import RULE_EVALUATORS, _LEGACY_EVALUATORS
from app.signals.registry import default_signal_registry

VALID_OPERATORS = {">=", ">", "<=", "<", "==", "!=", "="}
VALID_AGGREGATIONS = {"all", "any", "min", "max", "mean"}
VALID_SELECTIONS = {"all_members", "any_member", "team_lead"}
VALID_SEVERITIES = {"hard", "soft"}
VALID_ON_MISSING = {"manual_review", "fail", "pass", "skip"}

NUMERIC_SIGNAL_TYPES = {"integer", "float", "numeric"}
CONTAINER_SIGNAL_TYPES = {"list", "dict"}


def validate_rule_definition(rule: RuleDefinition) -> None:
    """Validate a single rule definition against schema and registry constraints."""
    r_type = rule.rule_type

    # 1. Unknown rule_type
    if r_type not in RULE_EVALUATORS and r_type not in _LEGACY_EVALUATORS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown rule_type '{r_type}'. Supported types: {sorted(RULE_EVALUATORS.keys())}.",
        )

    # 2. Severity validation
    sev = rule.severity.value if hasattr(rule.severity, "value") else str(rule.severity)
    if sev not in VALID_SEVERITIES:
        raise HTTPException(status_code=422, detail=f"Invalid severity '{sev}'. Must be 'hard' or 'soft'.")

    # 3. on_missing validation
    om = rule.on_missing.value if hasattr(rule.on_missing, "value") else str(rule.on_missing)
    if om not in VALID_ON_MISSING:
        raise HTTPException(status_code=422, detail=f"Invalid on_missing '{om}'. Must be one of {sorted(VALID_ON_MISSING)}.")

    # 4. Scope validation
    sc = rule.scope.value if hasattr(rule.scope, "value") else str(rule.scope)
    if r_type in ("team_size_min", "team_size_max"):
        if sc not in ("team", "team_level"):
            raise HTTPException(
                status_code=422,
                detail=f"Invalid scope '{sc}' for rule_type '{r_type}'. Team size rules require scope='team'.",
            )
    elif r_type == "duplicate_member_email":
        if sc != "cross_team":
            raise HTTPException(
                status_code=422,
                detail=f"Invalid scope '{sc}' for rule_type 'duplicate_member_email'. Must have scope='cross_team'.",
            )
    elif r_type == "track_limit":
        if sc not in ("cross_team", "team", "team_level"):
            raise HTTPException(
                status_code=422,
                detail=f"Invalid scope '{sc}' for rule_type 'track_limit'. Must have scope='cross_team' or 'team'.",
            )
    elif r_type in ("signal_threshold", "signal_contains", "required_link", "required_signal_present", "required_fields_present"):
        if sc in ("cross_team",):
            raise HTTPException(
                status_code=422,
                detail=f"Invalid scope '{sc}' for member-level rule '{r_type}'. Expected scope='member'.",
            )

    # 5. Member selection validation
    ms = rule.member_selection.value if rule.member_selection else rule.parameters.get("member_selection")
    if ms is not None and ms not in VALID_SELECTIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid member_selection '{ms}'. Supported: {sorted(VALID_SELECTIONS)}.",
        )
    if ms is not None and r_type in ("team_size_min", "team_size_max", "duplicate_member_email"):
        raise HTTPException(
            status_code=422,
            detail=f"member_selection is not applicable to rule_type '{r_type}'.",
        )

    # 6. Aggregation validation
    agg = rule.aggregation.value if rule.aggregation else rule.parameters.get("aggregation")
    if agg is not None:
        if r_type != "signal_threshold":
            raise HTTPException(
                status_code=422,
                detail=f"aggregation parameter is only valid for 'signal_threshold', not '{r_type}'.",
            )
        if agg not in VALID_AGGREGATIONS:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid aggregation '{agg}'. Supported: {sorted(VALID_AGGREGATIONS)}.",
            )

    params = rule.parameters or {}

    # Signal definitions from live registry (never hardcoded)
    all_registered_signals = {s.signal_key: s for s in default_signal_registry.list_signals()}

    # 7. Parameters validation per rule type
    if r_type == "team_size_min":
        if "min_size" not in params:
            raise HTTPException(status_code=422, detail="Missing required parameter 'min_size' for team_size_min.")
        val = params["min_size"]
        if isinstance(val, bool) or not isinstance(val, int) or val < 0:
            raise HTTPException(status_code=422, detail=f"Parameter 'min_size' must be a non-negative integer, got {repr(val)}.")

    elif r_type == "team_size_max":
        if "max_size" not in params:
            raise HTTPException(status_code=422, detail="Missing required parameter 'max_size' for team_size_max.")
        val = params["max_size"]
        if isinstance(val, bool) or not isinstance(val, int) or val < 1:
            raise HTTPException(status_code=422, detail=f"Parameter 'max_size' must be an integer >= 1, got {repr(val)}.")

    elif r_type == "required_link":
        link_field = params.get("link_field") or params.get("link_type")
        if not link_field or not isinstance(link_field, str) or not link_field.strip():
            raise HTTPException(status_code=422, detail="Missing or invalid parameter 'link_field' for required_link.")

    elif r_type == "required_signal_present":
        sig_key = params.get("signal_key")
        if not sig_key or not isinstance(sig_key, str) or not sig_key.strip():
            raise HTTPException(status_code=422, detail="Missing required parameter 'signal_key' for required_signal_present.")
        if sig_key not in all_registered_signals:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown signal key '{sig_key}'. Signal must be registered in default_signal_registry.",
            )

    elif r_type == "signal_threshold":
        sig_key = params.get("signal_key")
        if not sig_key or not isinstance(sig_key, str) or not sig_key.strip():
            raise HTTPException(status_code=422, detail="Missing required parameter 'signal_key' for signal_threshold.")
        if sig_key not in all_registered_signals:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown signal key '{sig_key}'. Signal must be registered in default_signal_registry.",
            )

        sig_def = all_registered_signals[sig_key]
        if sig_def.value_type not in NUMERIC_SIGNAL_TYPES:
            raise HTTPException(
                status_code=422,
                detail=f"Signal '{sig_key}' has value_type '{sig_def.value_type}', which is incompatible with numeric signal_threshold.",
            )

        op = params.get("operator")
        if not op or op not in VALID_OPERATORS:
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported operator '{op}' for signal_threshold. Supported: {sorted(VALID_OPERATORS)}.",
            )

        thresh = params.get("threshold")
        if thresh is None or isinstance(thresh, bool) or not isinstance(thresh, (int, float)) or math.isnan(thresh) or math.isinf(thresh):
            raise HTTPException(
                status_code=422,
                detail=f"Invalid threshold '{thresh}'. Must be a finite numeric value.",
            )

    elif r_type == "signal_contains":
        sig_key = params.get("signal_key")
        if not sig_key or not isinstance(sig_key, str) or not sig_key.strip():
            raise HTTPException(status_code=422, detail="Missing required parameter 'signal_key' for signal_contains.")
        if sig_key not in all_registered_signals:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown signal key '{sig_key}'. Signal must be registered in default_signal_registry.",
            )

        sig_def = all_registered_signals[sig_key]
        if sig_def.value_type not in CONTAINER_SIGNAL_TYPES:
            raise HTTPException(
                status_code=422,
                detail=f"Signal '{sig_key}' has value_type '{sig_def.value_type}', which is incompatible with signal_contains (must be 'list' or 'dict').",
            )

        exp_val = params.get("expected_value")
        if exp_val is None or (isinstance(exp_val, str) and not exp_val.strip()):
            raise HTTPException(status_code=422, detail="Missing required parameter 'expected_value' for signal_contains.")

    elif r_type == "allowed_values":
        allowed = params.get("allowed_values")
        if not allowed or not isinstance(allowed, list) or len(allowed) == 0:
            raise HTTPException(status_code=422, detail="Missing or empty 'allowed_values' list for allowed_values rule.")

        f_key = params.get("field_key")
        s_key = params.get("signal_key")
        if not f_key and not s_key:
            raise HTTPException(status_code=422, detail="allowed_values rule requires either 'field_key' or 'signal_key'.")

        if s_key and s_key not in all_registered_signals:
            raise HTTPException(status_code=422, detail=f"Unknown signal key '{s_key}' in allowed_values rule.")

    elif r_type == "track_limit":
        f_key = params.get("field_key")
        if not f_key or not isinstance(f_key, str) or not f_key.strip():
            raise HTTPException(status_code=422, detail="Missing required parameter 'field_key' for track_limit rule.")

        has_limits = "track_limits" in params and isinstance(params["track_limits"], dict) and len(params["track_limits"]) > 0
        has_single_limit = "limit" in params and isinstance(params["limit"], int) and params["limit"] >= 1
        if not has_limits and not has_single_limit:
            raise HTTPException(status_code=422, detail="track_limit rule requires valid 'track_limits' dictionary or 'limit' integer >= 1.")

    elif r_type == "required_fields_present":
        f_keys = params.get("field_keys")
        if not f_keys or not isinstance(f_keys, list) or len(f_keys) == 0:
            raise HTTPException(status_code=422, detail="Missing or empty 'field_keys' list for required_fields_present.")
        for k in f_keys:
            if not isinstance(k, str) or not k.strip():
                raise HTTPException(status_code=422, detail="All items in 'field_keys' must be non-empty strings.")


def validate_rule_configuration(config: RuleConfigurationCreate | RuleConfigurationUpdate) -> None:
    """Validate a full configuration bundle before persistence, raising HTTP 422 on violation."""
    if config.rules is not None:
        seen_rule_ids: set[str] = set()
        for rule in config.rules:
            if not rule.rule_id or not rule.rule_id.strip():
                raise HTTPException(status_code=422, detail="Every rule must have a non-empty 'rule_id'.")
            if rule.rule_id in seen_rule_ids:
                raise HTTPException(
                    status_code=422,
                    detail=f"Duplicate rule_id '{rule.rule_id}' found in configuration. Each rule_id must be unique.",
                )
            seen_rule_ids.add(rule.rule_id)
            validate_rule_definition(rule)
