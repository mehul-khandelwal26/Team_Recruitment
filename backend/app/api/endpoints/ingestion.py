"""Ingestion API endpoint.

POST /api/ingestion/upload
    Accepts a CSV or JSON file via multipart/form-data,
    validates its contents, and returns a structured response.
"""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.ingestion.parser import parse_csv, parse_json
from app.schemas.ingestion import UploadResponse

router = APIRouter(prefix="/api/ingestion", tags=["Ingestion"])

# Supported MIME types → parser mapping
_PARSERS = {
    "text/csv": parse_csv,
    "application/json": parse_json,
    # Common alternatives sent by browsers / tools
    "application/vnd.ms-excel": parse_csv,  # some systems tag .csv this way
}

# Fallback: decide by file extension when MIME type is ambiguous
_EXTENSION_MAP = {
    ".csv": parse_csv,
    ".json": parse_json,
}


@router.post("/upload", response_model=UploadResponse)
async def upload_registration_file(
    file: UploadFile = File(..., description="CSV or JSON registration file"),
) -> UploadResponse:
    """Accept a registration file, validate it, and return structured results.

    **Supported formats:**
    - **CSV** – one row per member (multipart/form-data, content-type ``text/csv``)
    - **JSON** – array of team objects (multipart/form-data, content-type ``application/json``)

    Returns validated teams, member counts, warnings for missing profile
    data, and errors for any invalid records.
    """
    # -- Determine the parser to use --------------------------------------
    parser = None

    # 1. Try content type
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    parser = _PARSERS.get(content_type)

    # 2. Fallback to file extension
    if parser is None and file.filename:
        ext = _get_extension(file.filename)
        parser = _EXTENSION_MAP.get(ext)

    if parser is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type: content_type='{file.content_type}', "
                f"filename='{file.filename}'. "
                "Please upload a .csv or .json file."
            ),
        )

    # -- Read file contents ------------------------------------------------
    raw_bytes = await file.read()

    # -- Parse & validate --------------------------------------------------
    result = parser(raw_bytes)

    # If there are only errors and no valid teams, return 422
    if not result.success and result.teams_count == 0:
        # Still return the structured body so the client can display errors
        return result

    return result


def _get_extension(filename: str) -> str:
    """Extract the lowercased file extension (e.g. '.csv')."""
    dot_idx = filename.rfind(".")
    if dot_idx == -1:
        return ""
    return filename[dot_idx:].lower()
