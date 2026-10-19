"""Database startup seeding for built-in rule and scoring presets in PostgreSQL mode.

Guarantees:
- Runs only when STORAGE_BACKEND is 'postgres'.
- Idempotently upserts standard built-in presets in a single transaction.
- Verifies required tables exist; if tables are missing, fails startup clearly
  without automatically running migrations or creating tables.
- Does not modify or deactivate user-created configurations.
- Reuses exact preset IDs and versions from get_default_presets() and get_default_scoring_presets().
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

from app.db.models import (
    RuleConfigurationModel,
    ScoringConfigurationModel,
    derive_rule_configuration_columns,
    derive_scoring_configuration_columns,
)
from app.db.session import create_app_engine, get_session_factory, session_scope

logger = logging.getLogger("app.db.seeding")


def seed_database_presets(engine: Optional[Engine] = None) -> None:
    """Idempotently seed standard built-in presets into PostgreSQL within a single transaction.

    Args:
        engine: Optional injected Engine. If None, uses create_app_engine().

    Raises:
        RuntimeError: If required database tables are missing or not migrated.
    """
    from app.rules.presets import get_default_presets
    from app.scoring.presets import get_default_scoring_presets
    target_engine = engine or create_app_engine()

    # 1. Verify schema tables exist
    inspector = inspect(target_engine)
    existing_tables = set(inspector.get_table_names())
    required_tables = {"rule_configurations", "scoring_configurations"}

    missing_tables = required_tables - existing_tables
    if missing_tables:
        raise RuntimeError(
            f"Database schema is incomplete (missing tables: {sorted(missing_tables)}). "
            "Please run 'alembic upgrade head' to apply migrations before starting the application."
        )

    # 2. Idempotent upserts within a single transaction
    factory = get_session_factory(target_engine)
    with session_scope(factory) as session:
        # A. Rule configuration presets
        rule_presets = get_default_presets()
        for preset in rule_presets:
            derived = derive_rule_configuration_columns(preset)
            stmt = pg_insert(RuleConfigurationModel).values(**derived)
            stmt = stmt.on_conflict_do_update(
                index_elements=["config_id", "version"],
                set_={
                    "name": stmt.excluded.name,
                    "description": stmt.excluded.description,
                    "updated_at": stmt.excluded.updated_at,
                    "payload": stmt.excluded.payload,
                },
            )
            session.execute(stmt)

        # B. Scoring configuration presets
        scoring_presets = get_default_scoring_presets()
        for preset in scoring_presets:
            derived = derive_scoring_configuration_columns(preset)
            stmt = pg_insert(ScoringConfigurationModel).values(**derived)
            stmt = stmt.on_conflict_do_update(
                index_elements=["config_id", "version"],
                set_={
                    "name": stmt.excluded.name,
                    "description": stmt.excluded.description,
                    "scale_max": stmt.excluded.scale_max,
                    "score_ineligible_teams": stmt.excluded.score_ineligible_teams,
                    "updated_at": stmt.excluded.updated_at,
                    "payload": stmt.excluded.payload,
                },
            )
            session.execute(stmt)

    logger.info(
        "Successfully verified/seeded built-in presets in PostgreSQL (%d rule presets, %d scoring presets).",
        len(rule_presets),
        len(scoring_presets),
    )
