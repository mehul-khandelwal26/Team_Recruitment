"""Alembic environment configuration.

Loads target metadata from app.db.base.Base and derives connection URL from
application configuration or explicit test override without logging credentials.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy import create_engine

# Ensure backend root is on sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.config import DATABASE_URL, normalize_database_url
from app.db.base import Base
import app.db.models

# Alembic Config object
config = context.config

# Interpret config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_target_url() -> str:
    """Resolve database URL from explicit override or application configuration.

    Never logs or exposes the URL string.
    """
    # 1. Explicit override passed in context attributes (used by migration tests)
    override = config.attributes.get("override_url")
    if override and isinstance(override, str) and override.strip():
        return normalize_database_url(override)

    # 2. Main option from config (if set programmatically)
    main_opt = config.get_main_option("sqlalchemy.url")
    if main_opt and main_opt.strip():
        return normalize_database_url(main_opt)

    # 3. Environment variable override
    env_override = os.getenv("ALEMBIC_DATABASE_URL")
    if env_override and env_override.strip():
        return normalize_database_url(env_override)

    # 4. Application direct DATABASE_URL
    db_url = os.getenv("DATABASE_URL", DATABASE_URL)
    if db_url and db_url.strip():
        return normalize_database_url(db_url)

    raise RuntimeError(
        "Alembic could not determine target database URL. "
        "DATABASE_URL must be configured or an explicit override supplied."
    )


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_target_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = config.attributes.get("connection", None)

    if connectable is None:
        url = get_target_url()
        connectable = create_engine(
            url,
            poolclass=pool.NullPool,
            connect_args={"connect_timeout": 10},
        )
        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
            )
            with context.begin_transaction():
                context.run_migrations()
    else:
        context.configure(
            connection=connectable,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
