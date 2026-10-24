"""FastAPI endpoints for weighted scoring, configuration management, and run auditing."""

from __future__ import annotations

from typing import Any, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.dependencies import get_current_user
from app.config import AUTH_ENABLED
from app.ingestion.store import default_dataset_store
from app.rules.store import get_effective_run
from app.schemas.auth import UserSchema
from app.scoring.config_store import default_scoring_config_store
from app.scoring.engine import evaluate_scoring
from app.scoring.schemas import (
    AggregationMethod,
    CriterionType,
    MissingDataPolicy,
    ScoringCatalogResponse,
    ScoringConfiguration,
    ScoringConfigurationCreate,
    ScoringConfigurationUpdate,
    ScoringEvaluationRequest,
    ScoringRunResponse,
)
from app.scoring.store import default_scoring_run_store
from app.scoring.validation import validate_scoring_configuration
from app.signals.flatten import flatten_extraction_signals
from app.signals.store import default_extraction_run_store

router = APIRouter(prefix="/api/scoring", tags=["Scoring"])


# ---------------------------------------------------------------------------
# 1. Catalog Endpoint
# ---------------------------------------------------------------------------


@router.get("/catalog", response_model=ScoringCatalogResponse)
def get_scoring_catalog() -> ScoringCatalogResponse:
    """Return catalog of all supported scoring criterion types, normalization methods,

    aggregation methods, and missing-data policies.
    """
    return ScoringCatalogResponse(
        criterion_types=[
            {
                "type": CriterionType.NUMERIC_RANGE.value,
                "name": "Numeric Range Mapping",
                "description": "Linear min-max normalization scaling numeric signals to [0.0, 1.0].",
                "supported_value_types": ["integer", "float"],
            },
            {
                "type": CriterionType.BOOLEAN.value,
                "name": "Boolean Mapping",
                "description": "Maps True and False states to configurable scores in [0.0, 1.0].",
                "supported_value_types": ["boolean"],
            },
            {
                "type": CriterionType.CATEGORICAL.value,
                "name": "Categorical Mapping",
                "description": "Explicit lookup table mapping discrete category names to scores in [0.0, 1.0].",
                "supported_value_types": ["string"],
            },
        ],
        normalization_methods=[
            {
                "method": "linear_range",
                "description": "Clamps value to [min_value, max_value] and scales linearly: (v - min) / (max - min).",
            },
            {
                "method": "boolean_mapping",
                "description": "Maps True -> true_score, False -> false_score.",
            },
            {
                "method": "categorical_mapping",
                "description": "Looks up category string in category_scores dictionary with optional fallback default.",
            },
        ],
        aggregation_methods=[
            {
                "method": AggregationMethod.MEAN.value,
                "name": "Mean (Average)",
                "description": "Calculates average of valid member scores across the team.",
            },
            {
                "method": AggregationMethod.MIN.value,
                "name": "Minimum",
                "description": "Uses the lowest valid member score as the team criterion score.",
            },
            {
                "method": AggregationMethod.MAX.value,
                "name": "Maximum",
                "description": "Uses the highest valid member score as the team criterion score.",
            },
            {
                "method": AggregationMethod.SUM.value,
                "name": "Sum (Clamped)",
                "description": "Sums valid member scores, clamped to max 1.0 to guarantee bounds safety.",
            },
            {
                "method": AggregationMethod.LEAD_ONLY.value,
                "name": "Team Lead Only",
                "description": "Uses designated team lead score. Lead is identified by lead_field.",
            },
            {
                "method": AggregationMethod.TOP_K.value,
                "name": "Top K Average",
                "description": "Averages the highest K valid member scores.",
            },
        ],
        missing_data_policies=[
            {
                "policy": MissingDataPolicy.EXCLUDE_AND_RENORMALIZE.value,
                "name": "Exclude and Renormalize",
                "description": "Excludes the missing criterion from denominator and renormalizes remaining weights.",
            },
            {
                "policy": MissingDataPolicy.ZERO_SCORE.value,
                "name": "Zero Score",
                "description": "Assigns a score of 0.0 and retains criterion in denominator with its configured weight.",
            },
        ],
    )


# ---------------------------------------------------------------------------
# 2. Configuration Management Endpoints
# ---------------------------------------------------------------------------


@router.get("/configs", response_model=list[ScoringConfiguration])
def list_scoring_configs(
    current_user: UserSchema = Depends(get_current_user),
) -> list[ScoringConfiguration]:
    """List latest versions of all stored scoring configurations."""
    user_id = current_user.user_id if AUTH_ENABLED else None
    return default_scoring_config_store.list_latest(user_id=user_id)


@router.post("/configs", response_model=ScoringConfiguration, status_code=status.HTTP_201_CREATED)
def create_scoring_config(
    payload: ScoringConfigurationCreate,
    current_user: UserSchema = Depends(get_current_user),
) -> ScoringConfiguration:
    """Create a new validated scoring configuration (starts at version 1)."""
    # Check if config_id already exists
    cfg_id = payload.config_id
    existing = default_scoring_config_store.get(cfg_id)
    if existing is not None:
        if not AUTH_ENABLED or getattr(existing, "user_id", None) in ("system", current_user.user_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Scoring configuration '{payload.config_id}' already exists. Use PUT to create a new version.",
            )
        else:
            disambiguated = f"{payload.config_id}_{current_user.user_id[:8]}"
            if default_scoring_config_store.get(disambiguated) is not None:
                disambiguated = f"{payload.config_id}_{uuid.uuid4().hex[:6]}"
            cfg_id = disambiguated

    user_id = current_user.user_id if AUTH_ENABLED else None
    config = ScoringConfiguration(
        config_id=cfg_id,
        user_id=user_id,
        name=payload.name,
        version=1,
        description=payload.description,
        criteria=payload.criteria,
        scale_max=payload.scale_max,
        lead_field=payload.lead_field,
        lead_values=payload.lead_values,
        score_ineligible_teams=payload.score_ineligible_teams,
    )

    validation_errors = validate_scoring_configuration(config)
    if validation_errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"errors": validation_errors},
        )

    return default_scoring_config_store.save(config, user_id=user_id)


@router.get("/configs/{config_id}", response_model=ScoringConfiguration)
def get_scoring_config(
    config_id: str,
    version: Optional[int] = Query(None, description="Optional explicit version number"),
    current_user: UserSchema = Depends(get_current_user),
) -> ScoringConfiguration:
    """Fetch a configuration by ID (latest version by default, or specific version)."""
    config = default_scoring_config_store.get(config_id, version=version)
    if config is None or (
        AUTH_ENABLED and getattr(config, "user_id", None) not in ("system", current_user.user_id)
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scoring configuration '{config_id}' (version: {version or 'latest'}) not found.",
        )
    return config


@router.put("/configs/{config_id}", response_model=ScoringConfiguration)
def update_scoring_config(
    config_id: str,
    payload: ScoringConfigurationUpdate,
    current_user: UserSchema = Depends(get_current_user),
) -> ScoringConfiguration:
    """Update a scoring configuration by creating a new immutable version."""
    current = default_scoring_config_store.get(config_id)
    if current is None or (
        AUTH_ENABLED and getattr(current, "user_id", None) not in ("system", current_user.user_id)
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scoring configuration '{config_id}' not found.",
        )

    if AUTH_ENABLED and getattr(current, "user_id", None) == "system":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System default scoring configurations cannot be modified. Create a custom configuration instead.",
        )

    # Construct preview for validation
    candidate_config = ScoringConfiguration(
        config_id=config_id,
        user_id=current.user_id,
        version=current.version + 1,
        name=payload.name if payload.name is not None else current.name,
        description=payload.description if payload.description is not None else current.description,
        criteria=[c.model_copy(deep=True) for c in (payload.criteria if payload.criteria is not None else current.criteria)],
        scale_max=payload.scale_max if payload.scale_max is not None else current.scale_max,
        lead_field=payload.lead_field if payload.lead_field is not None else current.lead_field,
        lead_values=list(payload.lead_values) if payload.lead_values is not None else list(current.lead_values),
        score_ineligible_teams=payload.score_ineligible_teams if payload.score_ineligible_teams is not None else current.score_ineligible_teams,
        is_active=payload.is_active if payload.is_active is not None else current.is_active,
    )

    validation_errors = validate_scoring_configuration(candidate_config)
    if validation_errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"errors": validation_errors},
        )

    effective_user_id = current_user.user_id if AUTH_ENABLED else None
    updated = default_scoring_config_store.update(config_id, payload, user_id=effective_user_id)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Update failed.")
    return updated


@router.get("/configs/{config_id}/versions", response_model=list[int])
def get_scoring_config_versions(
    config_id: str,
    current_user: UserSchema = Depends(get_current_user),
) -> list[int]:
    """List all available version numbers for a scoring configuration."""
    current = default_scoring_config_store.get(config_id)
    if current is None or (
        AUTH_ENABLED and getattr(current, "user_id", None) not in ("system", current_user.user_id)
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scoring configuration '{config_id}' not found.",
        )
    versions = default_scoring_config_store.list_versions(config_id)
    if not versions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scoring configuration '{config_id}' not found.",
        )
    return versions


@router.delete("/configs/{config_id}", response_model=dict[str, str])
def delete_scoring_configuration(
    config_id: str,
    current_user: UserSchema = Depends(get_current_user),
) -> dict[str, str]:
    """Soft-delete a scoring configuration by marking it inactive."""
    current = default_scoring_config_store.get(config_id)
    if current is None or (
        AUTH_ENABLED and getattr(current, "user_id", None) not in ("system", current_user.user_id)
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scoring configuration '{config_id}' not found.",
        )

    if AUTH_ENABLED and getattr(current, "user_id", None) == "system":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System default scoring configurations cannot be deleted.",
        )

    success = default_scoring_config_store.delete(config_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scoring configuration '{config_id}' not found.",
        )
    return {"message": f"Scoring configuration '{config_id}' marked inactive."}


# ---------------------------------------------------------------------------
# 3. Evaluation & Run Audit Endpoints
# ---------------------------------------------------------------------------


@router.post("/evaluate", response_model=ScoringRunResponse)
def evaluate_teams_endpoint(
    request: ScoringEvaluationRequest,
    current_user: UserSchema = Depends(get_current_user),
) -> ScoringRunResponse:
    """Evaluate teams against a scoring configuration and return detailed breakdowns."""
    config: Optional[ScoringConfiguration] = None

    if request.inline_config is not None:
        config = request.inline_config
        val_errors = validate_scoring_configuration(config)
        if val_errors:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"errors": val_errors},
            )
    else:
        cfg_id = request.config_id or "balanced"
        config = default_scoring_config_store.get(cfg_id, version=request.config_version)
        if config is None or (
            AUTH_ENABLED and getattr(config, "user_id", None) not in ("system", current_user.user_id)
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scoring configuration '{cfg_id}' (version: {request.config_version or 'latest'}) not found.",
            )
        if not config.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Scoring configuration '{cfg_id}' is inactive.",
            )

    is_inline = request.inline_config is not None

    # 1. Provenance inheritance
    if request.eligibility_run_id:
        elig_run = get_effective_run(request.eligibility_run_id)
        if elig_run is None or (
            AUTH_ENABLED and getattr(elig_run, "user_id", None) != current_user.user_id
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Eligibility run '{request.eligibility_run_id}' not found.",
            )
        elig_dataset_id = getattr(elig_run, "dataset_id", None)
        if request.dataset_id and elig_dataset_id and elig_dataset_id != request.dataset_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Eligibility run dataset_id '{elig_dataset_id}' does not match supplied dataset_id '{request.dataset_id}'.",
            )
        if request.dataset_id is None and elig_dataset_id:
            request.dataset_id = elig_dataset_id
        if request.extraction_run_id is None and getattr(elig_run, "extraction_run_id", None):
            request.extraction_run_id = elig_run.extraction_run_id

    # 2. Resolve teams
    teams_to_evaluate = request.teams
    if teams_to_evaluate is None:
        if request.dataset_id:
            ds = default_dataset_store.get(request.dataset_id)
            if ds is None or (
                AUTH_ENABLED and getattr(ds, "user_id", None) != current_user.user_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Dataset '{request.dataset_id}' not found.",
                )
            teams_to_evaluate = ds.payload.get("teams", [])
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Must provide either teams or dataset_id.",
            )

    # 3. Resolve signals
    signals_to_evaluate = request.signals
    if signals_to_evaluate is None and request.extraction_run_id:
        ext_run = default_extraction_run_store.get(request.extraction_run_id)
        if ext_run is None or (
            AUTH_ENABLED and getattr(ext_run, "user_id", None) != current_user.user_id
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Extraction run '{request.extraction_run_id}' not found.",
            )
        if request.dataset_id and getattr(ext_run, "dataset_id", None) and ext_run.dataset_id != request.dataset_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Extraction run dataset_id '{ext_run.dataset_id}' does not match supplied dataset_id '{request.dataset_id}'.",
            )
        signals_to_evaluate = flatten_extraction_signals(ext_run)
    elif signals_to_evaluate is not None and request.extraction_run_id:
        ext_run = default_extraction_run_store.get(request.extraction_run_id)
        if ext_run is None or (
            AUTH_ENABLED and getattr(ext_run, "user_id", None) != current_user.user_id
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Extraction run '{request.extraction_run_id}' not found.",
            )
        if request.dataset_id and getattr(ext_run, "dataset_id", None) and ext_run.dataset_id != request.dataset_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Extraction run dataset_id '{ext_run.dataset_id}' does not match supplied dataset_id '{request.dataset_id}'.",
            )


    result = evaluate_scoring(
        teams=teams_to_evaluate,
        signals=signals_to_evaluate,
        config=config,
        eligibility_run_id=request.eligibility_run_id,
        eligibility_results=request.eligibility_results,
    )
    result.config_source = "inline" if is_inline else "stored"
    result.config_snapshot = config.model_copy(deep=True) if is_inline else None
    result.eligibility_run_id = request.eligibility_run_id
    if request.dataset_id:
        result.dataset_id = request.dataset_id
    if request.extraction_run_id:
        result.extraction_run_id = request.extraction_run_id

    user_id = current_user.user_id if AUTH_ENABLED else None
    result.user_id = user_id

    # Persist in run store
    default_scoring_run_store.save(result, user_id=user_id)
    return result


@router.get("/runs/{run_id}", response_model=ScoringRunResponse)
def get_scoring_run(
    run_id: str,
    current_user: UserSchema = Depends(get_current_user),
) -> ScoringRunResponse:
    """Retrieve a recorded scoring run with all team scores and criteria breakdowns."""
    run_record = default_scoring_run_store.get(run_id)
    if run_record is None or (
        AUTH_ENABLED and getattr(run_record, "user_id", None) != current_user.user_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scoring run '{run_id}' not found.",
        )
    return run_record
