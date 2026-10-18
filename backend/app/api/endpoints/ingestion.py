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
from typing import Optional, Union
import uuid

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from app.ingestion.discovery import CANONICAL_FIELD_CATALOG, discover_fields_from_bytes
from app.ingestion.parser import parse_csv, parse_json
from app.ingestion.store import default_dataset_store
from app.schemas.ingestion import DatasetRecord, DatasetSummary, UploadResponse, ValidationError
from app.schemas.mapping import CanonicalFieldInfo, FieldDiscoveryResponse

router = APIRouter(prefix="/api/ingestion", tags=["Ingestion"])

# Supported MIME types -> parser mapping
_PARSERS = {
    "text/csv": parse_csv,
    "application/json": parse_json,
    "application/vnd.ms-excel": parse_csv,
}

_EXTENSION_MAP = {
    ".csv": parse_csv,
    ".json": parse_json,
}


@router.post("/upload", response_model=UploadResponse)
async def upload_registration_file(
    file: UploadFile = File(..., description="CSV or JSON registration file"),
    mapping: Optional[str] = Form(
        None,
        description="Optional JSON-encoded dictionary of field mappings (original_name -> target_field)",
    ),
    dataset_id: Optional[str] = Form(
        None,
        description="Optional explicit dataset identifier to assign to this upload",
    ),
) -> UploadResponse:
    """Accept a registration file, validate it, and return structured results.

    Supports optional explicit column/field mapping. Unmapped fields are
    preserved in ``custom_fields`` and ``raw_data`` without causing errors.
    If valid, persistently stores the dataset snapshot and returns dataset_id.
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

    raw_bytes = await file.read()
    result = parser(raw_bytes, mapping=mapping_dict)

    if result.success:
        ds_id = dataset_id.strip() if dataset_id and dataset_id.strip() else f"ds_{uuid.uuid4().hex[:12]}"
        file_type = "csv"
        content_type = (file.content_type or "").split(";")[0].strip().lower()
        if content_type == "application/json" or (file.filename and file.filename.lower().endswith(".json")):
            file_type = "json"

        now_dt = datetime.datetime.now(datetime.timezone.utc)
        record = DatasetRecord(
            dataset_id=ds_id,
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
        saved = default_dataset_store.save(record)
        result.dataset_id = saved.dataset_id

    return result


@router.get("/datasets/{dataset_id}", response_model=DatasetRecord)
async def get_dataset(dataset_id: str) -> DatasetRecord:
    """Retrieve an uploaded dataset snapshot by dataset_id."""
    record = default_dataset_store.get(dataset_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Dataset '{dataset_id}' not found.",
        )
    return record


@router.get("/datasets", response_model=Union[list[DatasetRecord], list[DatasetSummary]])
async def list_datasets(
    summary: bool = Query(default=False, description="Return lightweight summary objects without teams or payload"),
    limit: int = Query(default=50, ge=1, le=200, description="Maximum number of items to return (1-200)"),
) -> Union[list[DatasetRecord], list[DatasetSummary]]:
    """List all uploaded datasets ordered by upload timestamp."""
    if summary:
        return default_dataset_store.list_summaries(limit=limit)
    return default_dataset_store.list_datasets()



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

    raw_bytes = await file.read()
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
