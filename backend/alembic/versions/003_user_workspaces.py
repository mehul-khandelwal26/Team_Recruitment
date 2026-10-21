"""Add user_id column for user-isolated multi-tenant workspaces.

Revision ID: 003_user_workspaces
Revises: 002_add_users_table
Create Date: 2026-10-21 00:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "003_user_workspaces"
down_revision: Union[str, None] = "002_add_users_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = [
    "datasets",
    "extraction_runs",
    "eligibility_runs",
    "scoring_runs",
    "ranking_runs",
    "rule_configurations",
    "scoring_configurations",
]


def upgrade() -> None:
    for table_name in TABLES:
        # Add column if not exists (in case transaction rolled back or partially committed)
        op.execute(
            f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS user_id VARCHAR(64)"
        )
        op.execute(
            f"CREATE INDEX IF NOT EXISTS ix_{table_name}_user_id ON {table_name} (user_id)"
        )

    # Backfill existing records to 'dev-user' so existing dev data remains intact
    # for the Developer Quick Login, while new users start with clean workspaces.
    op.execute("UPDATE datasets SET user_id = 'dev-user' WHERE user_id IS NULL")
    op.execute("UPDATE extraction_runs SET user_id = 'dev-user' WHERE user_id IS NULL")
    op.execute("UPDATE eligibility_runs SET user_id = 'dev-user' WHERE user_id IS NULL")
    op.execute("UPDATE scoring_runs SET user_id = 'dev-user' WHERE user_id IS NULL")
    op.execute("UPDATE ranking_runs SET user_id = 'dev-user' WHERE user_id IS NULL")


def downgrade() -> None:
    for table_name in TABLES:
        op.drop_index(f"ix_{table_name}_user_id", table_name=table_name)
        op.drop_column(table_name, "user_id")
