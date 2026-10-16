"""Eligibility rules engine API endpoints.

Endpoints:
- GET /api/rules/catalog: List available rule types, schemas, and descriptors.
- GET /api/rules/configs: List active rule configurations (latest versions).
- POST /api/rules/configs: Create a new custom rule configuration.
- GET /api/rules/configs/{config_id}: Retrieve a configuration by ID and optional version.
- PUT /api/rules/configs/{config_id}: Update configuration (creates new immutable version).
- GET /api/rules/configs/{config_id}/versions: List all versions for a configuration.
- DELETE /api/rules/configs/{config_id}: Mark a configuration as inactive.
- POST /api/rules/evaluate: Evaluate teams and signals against a rule configuration.
- GET /api/rules/runs/{run_id}: Retrieve evaluation run results (with manual overrides applied).
- POST /api/rules/runs/{run_id}/teams/{team_id}/override: Apply a manual eligibility override.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.rules.config_store import default_config_store
from app.rules.engine import evaluate_teams
from app.rules.schemas import (
    EligibilityEvaluateRequest,
    EligibilityRunResponse,
    EligibilityStatus,
    ManualOverride,
    ManualOverrideCreate,
    RuleConfiguration,
    RuleConfigurationCreate,
    RuleConfigurationUpdate,
    RuleTypeCatalogItem,
)
from app.rules.store import default_override_store, default_run_store, get_effective_run
from app.rules.types import RULE_TYPE_CATALOG

router = APIRouter(prefix="/api/rules", tags=["Rules"])


# ---------------------------------------------------------------------------
# Catalog & Configuration Endpoints
# ---------------------------------------------------------------------------


@router.get("/catalog", response_model=list[RuleTypeCatalogItem])
async def get_rule_catalog() -> list[RuleTypeCatalogItem]:
    """Return catalog of available eligibility rule types, supported scopes, and parameters."""
    return RULE_TYPE_CATALOG


@router.get("/configs", response_model=list[RuleConfiguration])
async def list_configurations() -> list[RuleConfiguration]:
    """List the latest active version of all registered rule configurations."""
    return default_config_store.list_latest()


@router.post("/configs", response_model=RuleConfiguration, status_code=201)
async def create_configuration(payload: RuleConfigurationCreate) -> RuleConfiguration:
    """Create a new custom eligibility rule configuration (version 1)."""
    from app.rules.validation import validate_rule_configuration

    validate_rule_configuration(payload)

    cfg_id = payload.config_id or f"config_{uuid.uuid4().hex[:8]}"

    existing = default_config_store.get(cfg_id)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Configuration with ID '{cfg_id}' already exists. Use PUT to create a new version.",
        )

    now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    new_cfg = RuleConfiguration(
        config_id=cfg_id,
        version=1,
        name=payload.name,
        description=payload.description,
        global_config=payload.global_config,
        rules=payload.rules,
        is_active=True,
        created_at=now_ts,
        updated_at=now_ts,
    )

    return default_config_store.save(new_cfg)


@router.get("/configs/{config_id}", response_model=RuleConfiguration)
async def get_configuration(
    config_id: str,
    version: Optional[int] = Query(None, description="Optional specific version number"),
) -> RuleConfiguration:
    """Retrieve a rule configuration by ID. Returns latest version if version is omitted."""
    cfg = default_config_store.get(config_id, version=version)
    if cfg is None:
        raise HTTPException(
            status_code=404,
            detail=f"Configuration '{config_id}'" + (f" version {version}" if version else "") + " not found.",
        )
    return cfg


@router.put("/configs/{config_id}", response_model=RuleConfiguration)
async def update_configuration(
    config_id: str,
    payload: RuleConfigurationUpdate,
) -> RuleConfiguration:
    """Update a rule configuration.

    Guarantees immutability by creating a new version with an incremented version number.
    Previous versions are preserved unchanged.
    """
    from app.rules.validation import validate_rule_configuration

    validate_rule_configuration(payload)

    updated = default_config_store.update(config_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Configuration '{config_id}' not found.")
    return updated


@router.get("/configs/{config_id}/versions", response_model=list[int])
async def list_configuration_versions(config_id: str) -> list[int]:
    """List all available version numbers for a given configuration."""
    versions = default_config_store.list_versions(config_id)
    if not versions:
        raise HTTPException(status_code=404, detail=f"Configuration '{config_id}' not found.")
    return versions


@router.delete("/configs/{config_id}", response_model=dict[str, str])
async def delete_configuration(config_id: str) -> dict[str, str]:
    """Soft-delete a configuration by marking it inactive."""
    success = default_config_store.delete(config_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Configuration '{config_id}' not found.")
    return {"message": f"Configuration '{config_id}' marked inactive."}


# ---------------------------------------------------------------------------
# Evaluation Endpoints
# ---------------------------------------------------------------------------


@router.post("/evaluate", response_model=EligibilityRunResponse)
async def evaluate_eligibility(payload: EligibilityEvaluateRequest) -> EligibilityRunResponse:
    """Execute deterministic eligibility evaluation against teams and signals.

    - Resolves configuration by config_id (default: 'basic' preset) and optional version.
    - Evaluates all active rules in deterministic order.
    - Generates human-readable explanations per rule and overall team decision.
    - Persists the run record into the run store.
    """
    target_config_id = payload.config_id or "basic"
    config = default_config_store.get(target_config_id, version=payload.config_version)

    if config is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Configuration '{target_config_id}'"
                + (f" version {payload.config_version}" if payload.config_version else "")
                + " not found."
            ),
        )

    # Execute evaluation
    run_response = evaluate_teams(
        teams=payload.teams,
        signals=payload.signals,
        config=config,
        evaluated_at=payload.evaluated_at,
    )
    if payload.dataset_id:
        run_response.dataset_id = payload.dataset_id
    if payload.extraction_run_id:
        run_response.extraction_run_id = payload.extraction_run_id

    # Persist in run store
    default_run_store.save(run_response)

    return run_response


@router.get("/runs/{run_id}", response_model=EligibilityRunResponse)
async def get_run_results(run_id: str) -> EligibilityRunResponse:
    """Retrieve an evaluation run's results, with any manual overrides merged."""
    run_record = get_effective_run(run_id)
    if run_record is None:
        raise HTTPException(status_code=404, detail=f"Evaluation run '{run_id}' not found.")
    return run_record


@router.post("/runs/{run_id}/teams/{team_id}/override", response_model=ManualOverride)
async def apply_team_override(
    run_id: str,
    team_id: str,
    payload: ManualOverrideCreate,
) -> ManualOverride:
    """Apply an organizer's manual eligibility override to a team in an evaluation run.

    Requires a non-empty explanation reason. The original evaluation record remains immutable.
    """
    run_record = default_run_store.get(run_id)
    if run_record is None:
        raise HTTPException(status_code=404, detail=f"Evaluation run '{run_id}' not found.")

    team_target = next((t for t in run_record.teams if t.team_id == team_id), None)
    if team_target is None:
        raise HTTPException(
            status_code=404,
            detail=f"Team '{team_id}' not found in evaluation run '{run_id}'.",
        )

    clean_reason = payload.reason.strip()
    if not clean_reason:
        raise HTTPException(
            status_code=400,
            detail="A non-empty reason is mandatory for manual eligibility overrides.",
        )

    now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    override = ManualOverride(
        override_id=f"ovr_{uuid.uuid4().hex[:10]}",
        run_id=run_id,
        team_id=team_id,
        original_status=team_target.status,
        override_status=payload.override_status,
        reason=clean_reason,
        overridden_by=payload.overridden_by or "organizer",
        overridden_at=now_ts,
    )

    default_override_store.save(override)
    return override
