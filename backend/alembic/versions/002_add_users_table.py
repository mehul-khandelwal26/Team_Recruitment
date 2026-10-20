"""Add users table for authentication.

Revision ID: 002_add_users_table
Revises: 001_initial_schema
Create Date: 2026-10-21 00:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "002_add_users_table"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("google_sub", sa.String(length=128), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("picture_url", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("google_sub"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_google_sub", "users", ["google_sub"])


def downgrade() -> None:
    op.drop_index("ix_users_google_sub", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
