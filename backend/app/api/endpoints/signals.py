"""Signal extraction and catalog API endpoints.

Endpoints:
- GET /api/signals/catalog: Complete catalog of categories, analyzers, and supported signals.
- GET /api/signals/categories: List broad signal categories.
- GET /api/signals/analyzers: List registered signal analyzer descriptors.
- GET /api/signals/signals: List all supported individual signals.
- POST /api/signals/extract: Execute extraction on pre-parsed team structures.
- POST /api/signals/extract-file: Parse uploaded CSV/JSON and run selective signal extraction.
"""

from __future__ import annotations

import datetime
import json
from typing import Any, Optional, Union
import uuid

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from starlette.concurrency import run_in_threadpool

from app.api.endpoints.ingestion import _read_upload_file_bounded, _resolve_parser
from app.ingestion.store import default_dataset_store
from app.schemas.ingestion import DatasetRecord, MemberSchema, TeamSchema
from app.signals.flatten import flatten_extraction_signals
from app.signals.registry import default_signal_registry
from app.signals.schemas import (
    CategoryDefinition,
    ExtractionRunRequest,
    ExtractionRunResponse,
    ExtractionRunSummary,
    ExtractorDescriptor,
    SignalCatalogResponse,
    SignalDefinition,
)
from app.signals.store import default_extraction_run_store

router = APIRouter(prefix="/api/signals", tags=["Signals"])


@router.get("/catalog", response_model=SignalCatalogResponse)
async def get_signal_catalog() -> SignalCatalogResponse:
    """Return the complete catalog of available categories, analyzers, and signals.

    Allows organizers and frontend interfaces to inspect all capabilities,
    browse broad categories, and discover individually selectable signals.
    """
    return default_signal_registry.get_catalog()


@router.get("/categories", response_model=list[CategoryDefinition])
async def list_categories() -> list[CategoryDefinition]:
    """Return the list of broad signal categories (e.g. Technical, Academics)."""
    return default_signal_registry.list_categories()


@router.get("/analyzers", response_model=list[ExtractorDescriptor])
async def list_analyzers() -> list[ExtractorDescriptor]:
    """Return metadata descriptors of all registered analyzers."""
    return default_signal_registry.list_descriptors()


@router.get("/signals", response_model=list[SignalDefinition])
async def list_individual_signals() -> list[SignalDefinition]:
    """Return all individually selectable evaluation signals supported across analyzers."""
    return default_signal_registry.list_signals()


@router.post("/extract", response_model=ExtractionRunResponse)
async def extract_signals(request: ExtractionRunRequest) -> ExtractionRunResponse:
    """Execute signal extraction for teams and their members.

    Only runs the analyzers and signals explicitly requested in ``selected_signals``.
    Preserves all member and team associations without combining results into
    composite scores. Automatically persists the run into the extraction run store.
    """
    teams_to_extract = request.teams
    if teams_to_extract is None and request.dataset_id:
        ds = default_dataset_store.get(request.dataset_id)
        if ds is None:
            raise HTTPException(
                status_code=404,
                detail=f"Dataset '{request.dataset_id}' not found.",
            )
        teams_to_extract = ds.payload.get("teams", [])
    elif teams_to_extract is None:
        raise HTTPException(
            status_code=400,
            detail="Must provide either teams or dataset_id.",
        )

    response = await run_in_threadpool(
        default_signal_registry.execute_extraction,
        teams=teams_to_extract,
        selected_signals=request.selected_signals,
        config=request.config,
    )
    if request.dataset_id:
        response.dataset_id = request.dataset_id

    default_extraction_run_store.save(response)
    return response


@router.post("/flatten", response_model=list[dict[str, Any]])
async def flatten_signals(request: ExtractionRunResponse) -> list[dict[str, Any]]:
    """Flatten an ExtractionRunResponse into a list of member-signals dictionaries.

    Produces:
        [{"member_id": ..., "signals": [...]}]
    Enables API clients to pipe signal extraction outputs directly into
    /api/rules/evaluate and /api/scoring/evaluate without custom scripts.
    """
    return flatten_extraction_signals(request)


@router.post("/extract-file", response_model=ExtractionRunResponse)
async def extract_signals_from_file(
    file: UploadFile = File(..., description="CSV or JSON registration file"),
    mapping: Optional[str] = Form(
        None,
        description="Optional JSON-encoded dictionary of field mappings (original_name -> target_field)",
    ),
    selected_signals: Optional[str] = Form(
        None,
        description="Optional JSON array or comma-separated list of signal keys to extract",
    ),
    config: Optional[str] = Form(
        None,
        description="Optional JSON-encoded dictionary of analyzer configuration parameters",
    ),
) -> ExtractionRunResponse:
    """Upload a registration file and run signal extraction in a single request.

    Parses CSV/JSON using the dynamic ingestion engine, maps columns, and runs
    only the selected signals across all parsed teams and members.
    """
    parser = _resolve_parser(file)
    if parser is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type: content_type='{file.content_type}', "
                f"filename='{file.filename}'. "
                "Please upload a .csv or .json file."
            ),
        )

    # Parse optional mapping JSON
    mapping_dict: Optional[dict[str, str]] = None
    if mapping and mapping.strip():
        try:
            parsed_m = json.loads(mapping.strip())
            if isinstance(parsed_m, dict):
                mapping_dict = {str(k): str(v) for k, v in parsed_m.items()}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid mapping JSON: {exc}")

    # Parse optional selected_signals
    active_signals: Optional[list[str]] = None
    if selected_signals and selected_signals.strip():
        s_str = selected_signals.strip()
        if s_str.startswith("["):
            try:
                parsed_sigs = json.loads(s_str)
                if isinstance(parsed_sigs, list):
                    active_signals = [str(s) for s in parsed_sigs]
            except Exception:
                active_signals = [s.strip() for s in s_str.strip("[]").split(",") if s.strip()]
        else:
            active_signals = [s.strip() for s in s_str.split(",") if s.strip()]

    # Parse optional config
    config_dict: dict = {}
    if config and config.strip():
        try:
            parsed_cfg = json.loads(config.strip())
            if isinstance(parsed_cfg, dict):
                config_dict = parsed_cfg
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid config JSON: {exc}")

    raw_bytes = await _read_upload_file_bounded(file)
    upload_result = parser(raw_bytes, mapping=mapping_dict)

    if not upload_result.success:
        err_msgs = [e.message for e in upload_result.errors]
        return ExtractionRunResponse(
            run_id="failed_ingestion",
            teams=[],
            selected_signals=active_signals or [],
            analyzers_executed=[],
            total_teams=0,
            total_members=0,
            errors=err_msgs,
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )

    # Persist the valid uploaded dataset
    ds_id = f"ds_{uuid.uuid4().hex[:12]}"
    file_type = "csv"
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type == "application/json" or (file.filename and file.filename.lower().endswith(".json")):
        file_type = "json"

    now_dt = datetime.datetime.now(datetime.timezone.utc)
    ds_record = DatasetRecord(
        dataset_id=ds_id,
        filename=file.filename or f"uploaded.{file_type}",
        file_type=file_type,
        teams_count=upload_result.teams_count,
        members_count=upload_result.members_count,
        uploaded_at=now_dt.isoformat(),
        mapping=mapping_dict,
        warnings=[w.model_dump() for w in upload_result.warnings],
        unmapped_fields=upload_result.unmapped_fields,
        created_at=now_dt.isoformat(),
        payload=upload_result.model_dump(),
    )
    default_dataset_store.save(ds_record)

    run_response = await run_in_threadpool(
        default_signal_registry.execute_extraction,
        teams=upload_result.teams,
        selected_signals=active_signals,
        config=config_dict,
    )
    run_response.dataset_id = ds_id
    default_extraction_run_store.save(run_response)
    return run_response


@router.post("/extract-resume", response_model=ExtractionRunResponse)
async def extract_signals_from_resume_file(
    file: UploadFile = File(..., description="Resume document in PDF (.pdf) or DOCX (.docx) format"),
    candidate_name: Optional[str] = Form("Candidate", description="Optional display name for candidate"),
    member_id: Optional[str] = Form(None, description="Optional member identifier"),
    team_id: Optional[str] = Form(None, description="Optional team identifier"),
    selected_signals: Optional[str] = Form(
        None,
        description="Optional JSON array or comma-separated list of resume signal keys to extract",
    ),
    config: Optional[str] = Form(
        None,
        description="Optional JSON configuration dictionary",
    ),
) -> ExtractionRunResponse:
    """Extract signals directly from an uploaded PDF or DOCX resume document.

    Enforces file size limits (10 MB) and format validation (PDF, DOCX).
    Returns standardized ExtractionRunResponse with extracted signals.
    """
    filename = file.filename or "resume.pdf"

    # Validate file type extension
    lower_fn = filename.lower()
    if not (lower_fn.endswith(".pdf") or lower_fn.endswith(".docx")):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type for resume: '{filename}'. Only .pdf and .docx files are supported.",
        )

    raw_bytes = await file.read()
    if len(raw_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded resume file is empty (0 bytes).")
    if len(raw_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Uploaded resume file exceeds maximum size limit of 10 MB.")

    # Parse optional selected_signals
    active_signals: Optional[list[str]] = None
    if selected_signals and selected_signals.strip():
        s_str = selected_signals.strip()
        if s_str.startswith("["):
            try:
                parsed_sigs = json.loads(s_str)
                if isinstance(parsed_sigs, list):
                    active_signals = [str(s) for s in parsed_sigs]
            except Exception:
                active_signals = [s.strip() for s in s_str.strip("[]").split(",") if s.strip()]
        else:
            active_signals = [s.strip() for s in s_str.split(",") if s.strip()]

    # Parse optional config
    config_dict: dict = {}
    if config and config.strip():
        try:
            parsed_cfg = json.loads(config.strip())
            if isinstance(parsed_cfg, dict):
                config_dict = parsed_cfg
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid config JSON: {exc}")

    # Create temporary single-member team with resume_bytes in custom_fields
    m_id = member_id or "resume_member_1"
    t_id = team_id or "resume_team_1"
    c_name = candidate_name or "Candidate"

    single_member = MemberSchema(
        member_id=m_id,
        name=c_name,
        resume_url=filename,
        custom_fields={"resume_bytes": raw_bytes, "resume_filename": filename},
    )
    single_team = TeamSchema(
        team_id=t_id,
        team_name=f"Team_{c_name}",
        members=[single_member],
    )

    run_response = await run_in_threadpool(
        default_signal_registry.execute_extraction,
        teams=[single_team],
        selected_signals=active_signals,
        config=config_dict,
    )
    default_extraction_run_store.save(run_response)
    return run_response


@router.get("/runs/{run_id}", response_model=ExtractionRunResponse)
async def get_extraction_run(run_id: str) -> ExtractionRunResponse:
    """Retrieve a recorded signal extraction run with all team and member results."""
    record = default_extraction_run_store.get(run_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Extraction run '{run_id}' not found.",
        )
    return record


@router.get("/runs/{run_id}/dependencies")
async def get_extraction_run_dependencies(run_id: str) -> dict[str, Any]:
    """Retrieve counts of downstream evaluation runs dependent on this extraction run."""
    record = default_extraction_run_store.get(run_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Extraction run '{run_id}' not found.",
        )
    counts = default_extraction_run_store.get_dependent_counts(run_id)
    return {
        "run_id": run_id,
        "dataset_id": record.dataset_id,
        "dependencies": counts,
        "has_dependencies": counts.get("total", 0) > 0,
    }


@router.delete("/runs/{run_id}")
async def delete_extraction_run(
    run_id: str,
    cascade: bool = Query(default=False, description="Cascade delete all dependent scoring and ranking runs"),
) -> dict[str, Any]:
    """Permanently delete an extraction run and optionally cascade delete dependent runs."""
    record = default_extraction_run_store.get(run_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Extraction run '{run_id}' not found.",
        )

    counts = default_extraction_run_store.get_dependent_counts(run_id)
    if not cascade and counts.get("total", 0) > 0:
        raise HTTPException(
            status_code=409,
            detail={
                "message": f"Cannot delete extraction run '{run_id}' because it has {counts['total']} dependent run(s).",
                "run_id": run_id,
                "counts": counts,
                "hint": "Provide ?cascade=true to delete the extraction run and all associated downstream runs.",
            },
        )

    try:
        deleted = default_extraction_run_store.delete(run_id, cascade=cascade)
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Extraction run '{run_id}' could not be deleted.",
        )

    return {
        "success": True,
        "run_id": run_id,
        "dataset_id": record.dataset_id,
        "deleted_runs": counts if cascade else {},
        "message": f"Extraction run '{run_id}' deleted successfully.",
    }


@router.get("/runs", response_model=Union[list[ExtractionRunResponse], list[ExtractionRunSummary]])
async def list_extraction_runs(
    dataset_id: Optional[str] = Query(default=None, description="Optional dataset ID filter"),
    summary: bool = Query(default=False, description="Return lightweight summary objects without team results"),
    limit: int = Query(default=50, ge=1, le=200, description="Maximum number of items to return (1-200)"),
) -> Union[list[ExtractionRunResponse], list[ExtractionRunSummary]]:
    """List recorded extraction runs, optionally filtered by dataset_id."""
    if summary:
        return default_extraction_run_store.list_summaries(limit=limit, dataset_id=dataset_id)
    return default_extraction_run_store.list_runs(dataset_id=dataset_id)



