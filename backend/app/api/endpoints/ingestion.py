"""Ingestion and dynamic form discovery API endpoints.

Endpoints:
- POST /api/ingestion/upload: Upload CSV/JSON with optional field mapping.
- POST /api/ingestion/inspect: Inspect file schema, infer types, and suggest mappings.
- POST /api/ingestion/discover-fields: Alias for inspect endpoint.
- GET /api/ingestion/canonical-fields: List recognized application target fields.
"""

from __future__ import annotations

import datetime
import json
from typing import Any, Optional, Union
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

from app.auth.dependencies import get_current_user
from app.config import AUTH_ENABLED
from app.ingestion.discovery import CANONICAL_FIELD_CATALOG, discover_fields_from_bytes
from app.ingestion.parser import parse_csv, parse_json
from app.ingestion.store import default_dataset_store
from app.schemas.auth import UserSchema
from app.schemas.ingestion import DatasetRecord, DatasetSummary, UploadResponse, ValidationError
from app.schemas.mapping import CanonicalFieldInfo, FieldDiscoveryResponse

router = APIRouter(prefix="/api/ingestion", tags=["Ingestion"])

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB


async def _read_upload_file_bounded(file: UploadFile, max_bytes: int = MAX_UPLOAD_SIZE) -> bytes:
    """Read an uploaded file in chunks and enforce the maximum byte limit."""
    content = bytearray()
    while chunk := await file.read(1024 * 1024):
        content.extend(chunk)
        if len(content) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Uploaded file exceeds maximum size limit of {max_bytes // (1024 * 1024)} MB.",
            )
    return bytes(content)

# Supported MIME types -> parser mapping
_PARSERS = {
    "text/csv": parse_csv,
    "text/tab-separated-values": parse_csv,
    "text/plain": parse_csv,
    "application/json": parse_json,
    "application/vnd.ms-excel": parse_csv,
}

_EXTENSION_MAP = {
    ".csv": parse_csv,
    ".tsv": parse_csv,
    ".txt": parse_csv,
    ".json": parse_json,
}


@router.post("/upload", response_model=UploadResponse)
async def upload_registration_file(
    file: UploadFile = File(..., description="CSV or JSON registration file"),
    resumes_archive: Optional[UploadFile] = File(
        None,
        description="Optional companion ZIP archive containing candidate resume documents (PDF, DOCX)",
    ),
    mapping: Optional[str] = Form(
        None,
        description="Optional JSON-encoded dictionary of field mappings (original_name -> target_field)",
    ),
    dataset_id: Optional[str] = Form(
        None,
        description="Optional explicit dataset identifier to assign to this upload",
    ),
    current_user: UserSchema = Depends(get_current_user),
) -> UploadResponse:
    """Accept a registration file, validate it, and return structured results.

    Supports optional explicit column/field mapping. Unmapped fields are
    preserved in ``custom_fields`` and ``raw_data`` without causing errors.
    If valid, persistently stores the dataset snapshot and returns dataset_id.
    """
    if dataset_id and dataset_id.strip():
        existing = default_dataset_store.get(dataset_id.strip())
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Dataset with ID '{dataset_id.strip()}' already exists.",
            )

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

    # Parse optional companion resumes archive
    resumes_zip_bytes: Optional[bytes] = None
    if resumes_archive is not None:
        archive_name = (resumes_archive.filename or "").lower()
        if not archive_name.endswith(".zip"):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported companion archive type '{resumes_archive.filename}'. Only .zip archives are supported.",
            )
        resumes_zip_bytes = await _read_upload_file_bounded(resumes_archive, max_bytes=50 * 1024 * 1024)

    # Parse optional mapping JSON string
    mapping_dict: Optional[dict[str, str]] = None
    if mapping:
        mapping_str = mapping.strip()
        if mapping_str:
            try:
                parsed_mapping = json.loads(mapping_str)
                if not isinstance(parsed_mapping, dict):
                    raise ValueError("Mapping must be a JSON object mapping original names to canonical fields.")
                mapping_dict = {str(k): str(v) for k, v in parsed_mapping.items()}
            except Exception as exc:
                return UploadResponse(
                    success=False,
                    errors=[
                        ValidationError(
                            location="mapping",
                            message=f"Invalid field mapping JSON: {exc}",
                        )
                    ],
                )

    raw_bytes = await _read_upload_file_bounded(file)
    result = parser(raw_bytes, mapping=mapping_dict, resumes_zip_bytes=resumes_zip_bytes)

    if result.success:
        ds_id = dataset_id.strip() if dataset_id and dataset_id.strip() else f"ds_{uuid.uuid4().hex[:12]}"
        file_type = "csv"
        content_type = (file.content_type or "").split(";")[0].strip().lower()
        if content_type == "application/json" or (file.filename and file.filename.lower().endswith(".json")):
            file_type = "json"

        user_id = current_user.user_id if AUTH_ENABLED else None
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        record = DatasetRecord(
            dataset_id=ds_id,
            user_id=user_id,
            filename=file.filename or f"uploaded.{file_type}",
            file_type=file_type,
            teams_count=result.teams_count,
            members_count=result.members_count,
            uploaded_at=now_dt.isoformat(),
            mapping=mapping_dict,
            warnings=[w.model_dump() for w in result.warnings],
            unmapped_fields=result.unmapped_fields,
            created_at=now_dt.isoformat(),
            payload=result.model_dump(),
        )
        saved = default_dataset_store.save(record, user_id=user_id)
        result.dataset_id = saved.dataset_id
        result.mapping = saved.mapping

    return result


@router.get("/datasets/{dataset_id}", response_model=DatasetRecord)
async def get_dataset(
    dataset_id: str,
    current_user: UserSchema = Depends(get_current_user),
) -> DatasetRecord:
    """Retrieve an uploaded dataset snapshot by dataset_id."""
    record = default_dataset_store.get(dataset_id)
    if record is None or (
        AUTH_ENABLED and getattr(record, "user_id", None) != current_user.user_id
    ):
        raise HTTPException(
            status_code=404,
            detail=f"Dataset '{dataset_id}' not found.",
        )
    return record


@router.get("/datasets/{dataset_id}/dependencies")
async def get_dataset_dependencies(
    dataset_id: str,
    current_user: UserSchema = Depends(get_current_user),
) -> dict[str, Any]:
    """Retrieve counts of downstream evaluation runs dependent on this dataset."""
    record = default_dataset_store.get(dataset_id)
    if record is None or (
        AUTH_ENABLED and getattr(record, "user_id", None) != current_user.user_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' not found.",
        )
    counts = default_dataset_store.get_dependent_counts(dataset_id)
    return {
        "dataset_id": dataset_id,
        "filename": record.filename,
        "dependencies": counts,
        "has_dependencies": counts.get("total", 0) > 0,
    }


@router.delete("/datasets/{dataset_id}")
async def delete_dataset(
    dataset_id: str,
    cascade: bool = Query(default=False, description="Cascade delete all associated runs"),
    current_user: UserSchema = Depends(get_current_user),
) -> dict[str, Any]:
    """Permanently delete an uploaded dataset and optionally cascade delete dependent runs."""
    record = default_dataset_store.get(dataset_id)
    if record is None or (
        AUTH_ENABLED and getattr(record, "user_id", None) != current_user.user_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' not found.",
        )

    counts = default_dataset_store.get_dependent_counts(dataset_id)
    if not cascade and counts.get("total", 0) > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": f"Cannot delete dataset '{dataset_id}' because it has {counts['total']} dependent run(s).",
                "dataset_id": dataset_id,
                "counts": counts,
                "hint": "Provide ?cascade=true to delete the dataset and all associated runs.",
            },
        )

    try:
        deleted = default_dataset_store.delete(dataset_id, cascade=cascade)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' could not be deleted.",
        )

    return {
        "success": True,
        "dataset_id": dataset_id,
        "filename": record.filename,
        "deleted_runs": counts if cascade else {},
        "message": f"Dataset '{record.filename}' ({dataset_id}) deleted successfully.",
    }


@router.get("/datasets", response_model=Union[list[DatasetRecord], list[DatasetSummary]])
async def list_datasets(
    summary: bool = Query(default=False, description="Return lightweight summary objects without teams or payload"),
    limit: int = Query(default=50, ge=1, le=200, description="Maximum number of items to return (1-200)"),
    current_user: UserSchema = Depends(get_current_user),
) -> Union[list[DatasetRecord], list[DatasetSummary]]:
    """List all uploaded datasets ordered by upload timestamp."""
    user_id = current_user.user_id if AUTH_ENABLED else None
    if summary:
        return default_dataset_store.list_summaries(limit=limit, user_id=user_id)
    return default_dataset_store.list_datasets(user_id=user_id)



@router.post("/inspect", response_model=FieldDiscoveryResponse)
async def inspect_registration_file(
    file: UploadFile = File(..., description="CSV or JSON registration file to inspect"),
) -> FieldDiscoveryResponse:
    """Inspect an uploaded file's schema without committing to ingestion.

    Discovers original column names, computes population statistics,
    infers basic data types, and suggests canonical field mappings.
    """
    file_type = "csv"
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type == "application/json" or (file.filename and file.filename.lower().endswith(".json")):
        file_type = "json"

    raw_bytes = await _read_upload_file_bounded(file)
    filename = file.filename or f"uploaded.{file_type}"

    return discover_fields_from_bytes(raw_bytes, file_name=filename, file_type=file_type)


@router.post("/discover-fields", response_model=FieldDiscoveryResponse, include_in_schema=False)
async def discover_fields_alias(
    file: UploadFile = File(..., description="CSV or JSON registration file to inspect"),
) -> FieldDiscoveryResponse:
    """Convenience alias for /inspect endpoint."""
    return await inspect_registration_file(file=file)


@router.get("/canonical-fields", response_model=list[CanonicalFieldInfo])
async def list_canonical_fields() -> list[CanonicalFieldInfo]:
    """Return the catalog of recognized canonical application target fields.

    Useful for frontends to populate mapping dropdown menus.
    """
    return CANONICAL_FIELD_CATALOG


def _resolve_parser(file: UploadFile):
    """Determine parser by MIME type or file extension."""
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    parser = _PARSERS.get(content_type)
    if parser is None and file.filename:
        ext = _get_extension(file.filename)
        parser = _EXTENSION_MAP.get(ext)
    return parser


def _get_extension(filename: str) -> str:
    """Extract lowercased file extension."""
    dot_idx = filename.rfind(".")
    if dot_idx == -1:
        return ""
    return filename[dot_idx:].lower()
