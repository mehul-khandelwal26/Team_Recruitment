"""Fix multi-tenant configuration isolation and backfill preset user_id.

Revision ID: 004_fix_tenant_config_isolation
Revises: 003_user_workspaces
Create Date: 2026-10-22 00:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "004_fix_tenant_config_isolation"
down_revision: Union[str, None] = "003_user_workspaces"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SYSTEM_SCORING_PRESETS = ("balanced", "technical_heavy", "academic_heavy", "edge_scoring_model")
SYSTEM_RULE_PRESETS = ("basic", "strict", "open_solo", "demo_mixed_review")


def upgrade() -> None:
    # 1. Backfill system presets in scoring_configurations
    scoring_ids_str = ", ".join(f"'{p}'" for p in SYSTEM_SCORING_PRESETS)
    op.execute(
        f"UPDATE scoring_configurations SET user_id = 'system' WHERE config_id IN ({scoring_ids_str})"
    )

    # 2. Backfill system presets in rule_configurations
    rule_ids_str = ", ".join(f"'{p}'" for p in SYSTEM_RULE_PRESETS)
    op.execute(
        f"UPDATE rule_configurations SET user_id = 'system' WHERE config_id IN ({rule_ids_str})"
    )

    # 3. Backfill any custom configurations with user_id NULL to 'dev-user'
    op.execute(
        f"UPDATE scoring_configurations SET user_id = 'dev-user' WHERE user_id IS NULL OR (user_id = 'system' AND config_id NOT IN ({scoring_ids_str}))"
    )
    op.execute(
        f"UPDATE rule_configurations SET user_id = 'dev-user' WHERE user_id IS NULL OR (user_id = 'system' AND config_id NOT IN ({rule_ids_str}))"
    )

    # 4. Synchronize JSONB payload user_id with relational column
    op.execute(
        "UPDATE scoring_configurations SET payload = jsonb_set(payload, '{user_id}', to_jsonb(user_id)) WHERE payload->>'user_id' IS DISTINCT FROM user_id"
    )
    op.execute(
        "UPDATE rule_configurations SET payload = jsonb_set(payload, '{user_id}', to_jsonb(user_id)) WHERE payload->>'user_id' IS DISTINCT FROM user_id"
    )


def downgrade() -> None:
    pass
