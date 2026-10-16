"""Database engine creation, session management, and safety utilities.

Invariants:
- Uses Psycopg 3 driver with required SSL.
- pool_pre_ping=True and pool_recycle=300 to tolerate idle connection severing and Neon compute wake-up.
- pool_size=5 and max_overflow=2 for connection limit safety.
- Optional DATABASE_URL_POOLED supported with prepare_threshold=None (never applied to direct URL).
- session_scope() context manager for atomic, short-lived transactional scopes.
"""

from __future__ import annotations

from contextlib import contextmanager
import os
from typing import Any, Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DatabaseError, OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.config import (
    DATABASE_URL,
    DATABASE_URL_POOLED,
    assert_safe_test_database,
    normalize_database_url,
)

__all__ = [
    "create_app_engine",
    "get_session_factory",
    "session_scope",
    "assert_safe_test_database",
    "is_database_unavailable_error",
]


def create_app_engine(
    url: str | None = None,
    *,
    is_pooled: bool | None = None,
    connect_timeout: int = 10,
    **engine_kwargs: Any,
) -> Engine:
    """Create a configured SQLAlchemy engine for application or migration workloads.

    Args:
        url: Database URL. If None, resolves from DATABASE_URL_POOLED or DATABASE_URL.
        is_pooled: Explicit flag whether the target URL is a pooled connection (e.g. PgBouncer).
                   If True, adds prepare_threshold=None for Psycopg 3 compatibility.
        connect_timeout: Seconds to wait when opening connections (default: 10s).
        **engine_kwargs: Additional arguments passed directly to SQLAlchemy create_engine.
    """
    effective_url = url
    effective_pooled = is_pooled

    if effective_url is None:
        pooled_env = os.getenv("DATABASE_URL_POOLED", DATABASE_URL_POOLED)
        direct_env = os.getenv("DATABASE_URL", DATABASE_URL)

        if pooled_env and pooled_env.strip():
            effective_url = pooled_env.strip()
            if effective_pooled is None:
                effective_pooled = True
        elif direct_env and direct_env.strip():
            effective_url = direct_env.strip()
            if effective_pooled is None:
                effective_pooled = False
        else:
            raise RuntimeError(
                "Unable to create database engine: No DATABASE_URL or DATABASE_URL_POOLED configured."
            )

    normalized_url = normalize_database_url(effective_url)

    connect_args: dict[str, Any] = {"connect_timeout": connect_timeout}
    if effective_pooled is True:
        # Psycopg 3 with transaction-pooled Neon/PgBouncer requires disabling server-side prepared statements
        connect_args["prepare_threshold"] = None

    default_engine_kwargs: dict[str, Any] = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 5,
        "max_overflow": 2,
        "connect_args": connect_args,
    }
    default_engine_kwargs.update(engine_kwargs)

    return create_engine(normalized_url, **default_engine_kwargs)


def get_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    """Create a thread-safe sessionmaker bound to the given or newly created engine."""
    target_engine = engine or create_app_engine()
    return sessionmaker(bind=target_engine, autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope(
    session_factory: sessionmaker[Session] | None = None,
) -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of database operations.

    Yields a Session, automatically commits upon normal exit, rolls back on any exception,
    and unconditionally closes the session in finally block.
    """
    factory = session_factory or get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def is_database_unavailable_error(exc: Exception) -> bool:
    """Return True if an exception indicates a persistent or transient database connection failure."""
    if isinstance(exc, (OperationalError, DatabaseError)):
        return True
    return False
