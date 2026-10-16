"""Centralized safe exception handling for database operations.

Translates SQLAlchemy and PostgreSQL exceptions into standard, secure API responses:
- Database unavailable / connection failure -> 503 Service Unavailable
- Foreign key violation -> 409 Conflict ("Referenced record does not exist or cannot be modified")
- Unique constraint violation -> 409 Conflict ("Record already exists or violates uniqueness constraint")
- Generic database error -> 500 Internal Server Error

Security:
- Never exposes SQL statements, parameters, URLs, passwords, or driver messages in responses.
- Logs only the exception class name and minimal non-sensitive context.
"""

from __future__ import annotations

import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DatabaseError, IntegrityError, OperationalError, SQLAlchemyError

from app.db.session import is_database_unavailable_error

logger = logging.getLogger("app.db.errors")


def register_database_error_handlers(app: FastAPI) -> None:
    """Register application-level database exception handlers on the FastAPI app."""

    @app.exception_handler(OperationalError)
    async def operational_error_handler(request: Request, exc: OperationalError) -> JSONResponse:
        logger.error("Database operational error: %s", exc.__class__.__name__)
        return JSONResponse(
            status_code=503,
            content={"detail": "Database temporarily unavailable"},
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
        logger.error("Database integrity error: %s", exc.__class__.__name__)
        orig = getattr(exc, "orig", None)
        sqlstate = getattr(orig, "sqlstate", None)

        # 23503 = foreign_key_violation in PostgreSQL
        if sqlstate == "23503" or "ForeignKeyViolation" in type(orig).__name__:
            return JSONResponse(
                status_code=409,
                content={"detail": "Referenced record does not exist or cannot be modified"},
            )

        # 23505 = unique_violation in PostgreSQL
        if sqlstate == "23505" or "UniqueViolation" in type(orig).__name__:
            return JSONResponse(
                status_code=409,
                content={"detail": "Record already exists or violates uniqueness constraint"},
            )

        return JSONResponse(
            status_code=409,
            content={"detail": "Data integrity conflict"},
        )

    @app.exception_handler(DatabaseError)
    async def database_error_handler(request: Request, exc: DatabaseError) -> JSONResponse:
        logger.error("Database error: %s", exc.__class__.__name__)
        if is_database_unavailable_error(exc):
            return JSONResponse(
                status_code=503,
                content={"detail": "Database temporarily unavailable"},
            )
        return JSONResponse(
            status_code=500,
            content={"detail": "An unexpected database error occurred"},
        )

    @app.exception_handler(SQLAlchemyError)
    async def generic_sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.error("SQLAlchemy error: %s", exc.__class__.__name__)
        return JSONResponse(
            status_code=500,
            content={"detail": "An unexpected database error occurred"},
        )
