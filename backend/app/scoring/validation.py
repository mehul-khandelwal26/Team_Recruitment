"""Validation logic for scoring configurations.

Ensures:
- No duplicate criterion IDs.
- Valid weights (finite, non-negative, total enabled weight > 0).
- Signal keys exist in default_signal_registry.
- Signal type compatibility with chosen CriterionType.
- Valid normalization settings (e.g. max_value > min_value for linear range).
- Valid aggregation settings (e.g. top_k requires positive integer K).
"""

from __future__ import annotations

import math
from typing import Optional

from app.scoring.schemas import (
    AggregationMethod,
    CriterionType,
    EvaluationCriterion,
    ScoringConfiguration,
)
from app.signals.registry import default_signal_registry


# Compatible signal value_types per CriterionType
_NUMERIC_SIGNAL_TYPES = {"integer", "float"}
_BOOLEAN_SIGNAL_TYPES = {"boolean"}
_CATEGORICAL_SIGNAL_TYPES = {"string"}


def validate_scoring_criterion(criterion: EvaluationCriterion) -> list[str]:
    """Validate an individual criterion against the signal registry and domain rules."""
    errors: list[str] = []

    # 1. Weight validation
    if math.isnan(criterion.weight) or math.isinf(criterion.weight):
        errors.append(f"Criterion '{criterion.criterion_id}': weight must be a finite number; got {criterion.weight}")
    elif criterion.weight < 0.0:
        errors.append(f"Criterion '{criterion.criterion_id}': weight must be non-negative; got {criterion.weight}")

    # 2. Signal key validation against default_signal_registry or custom signal prefix
    all_defs = {sig.signal_key: sig for sig in default_signal_registry.list_signals()}
    is_custom = criterion.target_signal_key.startswith("custom:") or criterion.target_signal_key.startswith("custom_")

    if not is_custom and criterion.target_signal_key not in all_defs:
        errors.append(
            f"Criterion '{criterion.criterion_id}': unknown target_signal_key '{criterion.target_signal_key}'. "
            f"Must be a registered signal in the signal catalog or prefixed with 'custom:'."
        )
    else:
        sig_def = all_defs.get(criterion.target_signal_key)
        val_type = sig_def.value_type if sig_def else "string"

        # 3. Type compatibility
        if criterion.criterion_type in (CriterionType.NUMERIC_RANGE, CriterionType.NUMERIC_WEIGHT):
            if not is_custom and val_type not in _NUMERIC_SIGNAL_TYPES:
                errors.append(
                    f"Criterion '{criterion.criterion_id}': criterion_type '{criterion.criterion_type.value}' "
                    f"is incompatible with signal '{criterion.target_signal_key}' of type '{val_type}'. "
                    f"Expected one of {_NUMERIC_SIGNAL_TYPES}."
                )
            # Normalization config check
            lr = criterion.normalization.linear_range
            if lr is None:
                errors.append(
                    f"Criterion '{criterion.criterion_id}': linear_range normalization config is required for numeric_range criterion."
                )
            else:
                if math.isnan(lr.min_value) or math.isinf(lr.min_value):
                    errors.append(f"Criterion '{criterion.criterion_id}': linear_range.min_value must be finite.")
                if math.isnan(lr.max_value) or math.isinf(lr.max_value):
                    errors.append(f"Criterion '{criterion.criterion_id}': linear_range.max_value must be finite.")
                if lr.max_value <= lr.min_value:
                    errors.append(
                        f"Criterion '{criterion.criterion_id}': linear_range.max_value ({lr.max_value}) "
                        f"must be strictly greater than min_value ({lr.min_value})."
                    )

        elif criterion.criterion_type in (CriterionType.BOOLEAN, CriterionType.BOOLEAN_BONUS):
            if not is_custom and val_type not in _BOOLEAN_SIGNAL_TYPES:
                errors.append(
                    f"Criterion '{criterion.criterion_id}': criterion_type 'boolean' is incompatible "
                    f"with signal '{criterion.target_signal_key}' of type '{val_type}'. Expected boolean."
                )

        elif criterion.criterion_type in (CriterionType.CATEGORICAL, CriterionType.CATEGORY_MATCH):
            if not is_custom and val_type not in _CATEGORICAL_SIGNAL_TYPES:
                errors.append(
                    f"Criterion '{criterion.criterion_id}': criterion_type 'categorical' is incompatible "
                    f"with signal '{criterion.target_signal_key}' of type '{val_type}'. Expected string."
                )
            cm = criterion.normalization.categorical_mapping
            has_exp = bool(criterion.config and criterion.config.get("expected_values"))
            if (cm is None or not cm.category_scores) and not has_exp:
                errors.append(
                    f"Criterion '{criterion.criterion_id}': categorical_mapping with non-empty category_scores "
                    f"or expected_values is required for categorical criterion."
                )

    # 4. Aggregation validation
    if criterion.aggregation == AggregationMethod.TOP_K:
        if criterion.top_k_value is None or criterion.top_k_value < 1:
            errors.append(
                f"Criterion '{criterion.criterion_id}': aggregation 'top_k' requires a positive integer top_k_value >= 1."
            )

    # 5. Confidence configuration validation
    if criterion.confidence_adjustment and criterion.confidence_adjustment.enabled:
        mc = criterion.confidence_adjustment.min_confidence
        if mc is not None and (mc < 0.0 or mc > 1.0 or math.isnan(mc) or math.isinf(mc)):
            errors.append(
                f"Criterion '{criterion.criterion_id}': confidence_adjustment.min_confidence must be between 0.0 and 1.0."
            )

    return errors


def validate_scoring_configuration(config: ScoringConfiguration) -> list[str]:
    """Validate a complete scoring configuration. Returns a list of error messages."""
    errors: list[str] = []

    if not config.config_id or not config.config_id.strip():
        errors.append("config_id cannot be blank.")
    if not config.name or not config.name.strip():
        errors.append("name cannot be blank.")
    if config.scale_max <= 0.0 or math.isnan(config.scale_max) or math.isinf(config.scale_max):
        errors.append(f"scale_max must be a positive finite number; got {config.scale_max}")

    # Duplicate criterion IDs
    seen_ids: set[str] = set()
    enabled_criteria: list[EvaluationCriterion] = []

    for criterion in config.criteria:
        cid = criterion.criterion_id
        if cid in seen_ids:
            errors.append(f"Duplicate criterion_id '{cid}' detected in configuration.")
        seen_ids.add(cid)

        if criterion.is_enabled:
            enabled_criteria.append(criterion)

        # Validate criterion details
        crit_errors = validate_scoring_criterion(criterion)
        errors.extend(crit_errors)

    # Total weight validation
    if not enabled_criteria:
        errors.append("Configuration must contain at least one enabled criterion.")
    else:
        total_enabled_weight = sum(c.weight for c in enabled_criteria)
        if total_enabled_weight <= 0.0:
            errors.append(
                f"Total weight of all enabled criteria must be strictly greater than 0; got {total_enabled_weight}"
            )

    return errors
