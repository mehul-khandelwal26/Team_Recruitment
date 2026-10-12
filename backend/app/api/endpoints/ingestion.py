"""Ingestion and dynamic form discovery API endpoints.

Endpoints:
- POST /api/ingestion/upload: Upload CSV/JSON with optional field mapping.
- POST /api/ingestion/inspect: Inspect file schema, infer types, and suggest mappings.
- POST /api/ingestion/discover-fields: Alias for inspect endpoint.
- GET /api/ingestion/canonical-fields: List recognized application target fields.
"""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.ingestion.discovery import CANONICAL_FIELD_CATALOG, discover_fields_from_bytes
from app.ingestion.parser import parse_csv, parse_json
from app.schemas.ingestion import UploadResponse, ValidationError
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
) -> UploadResponse:
    """Accept a registration file, validate it, and return structured results.

    Supports optional explicit column/field mapping. Unmapped fields are
    preserved in ``custom_fields`` and ``raw_data`` without causing errors.
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

    return result


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
