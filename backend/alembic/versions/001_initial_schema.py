"""Initial database schema migration.

Revision ID: 001_initial_schema
Revises: None
Create Date: 2026-10-17 00:00:00.000000

Creates the 8 core tables:
1. rule_configurations
2. scoring_configurations
3. datasets
4. extraction_runs
5. eligibility_runs
6. manual_overrides
7. scoring_runs
8. ranking_runs
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. rule_configurations
    op.create_table(
        "rule_configurations",
        sa.Column("config_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("config_id", "version", name="pk_rule_configurations"),
    )
    op.create_index(
        "ix_rule_configs_active",
        "rule_configurations",
        ["config_id", "is_active"],
    )
    op.create_index(
        "ix_rule_configs_version",
        "rule_configurations",
        ["config_id", sa.text("version DESC")],
    )

    # 2. scoring_configurations
    op.create_table(
        "scoring_configurations",
        sa.Column("config_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("scale_max", sa.Numeric(precision=6, scale=2), nullable=False, server_default="100.0"),
        sa.Column("score_ineligible_teams", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("config_id", "version", name="pk_scoring_configurations"),
    )
    op.create_index(
        "ix_scoring_configs_active",
        "scoring_configurations",
        ["config_id", "is_active"],
    )
    op.create_index(
        "ix_scoring_configs_version",
        "scoring_configurations",
        ["config_id", sa.text("version DESC")],
    )

    # 3. datasets
    op.create_table(
        "datasets",
        sa.Column("dataset_id", sa.String(length=64), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=16), nullable=False),
        sa.Column("teams_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("members_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mapping", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("unmapped_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("dataset_id", name="pk_datasets"),
    )
    op.create_index(
        "ix_datasets_uploaded",
        "datasets",
        [sa.text("uploaded_at DESC")],
    )

    # 4. extraction_runs
    op.create_table(
        "extraction_runs",
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("dataset_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("selected_signals", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("analyzers_executed", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("total_teams", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_members", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("run_id", name="pk_extraction_runs"),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.dataset_id"], name="fk_extraction_runs_dataset", ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_extraction_runs_dataset",
        "extraction_runs",
        ["dataset_id"],
    )
    op.create_index(
        "ix_extraction_runs_created",
        "extraction_runs",
        [sa.text("created_at DESC")],
    )

    # 5. eligibility_runs
    op.create_table(
        "eligibility_runs",
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("config_id", sa.String(length=64), nullable=False),
        sa.Column("config_version", sa.Integer(), nullable=False),
        sa.Column("dataset_id", sa.String(length=64), nullable=True),
        sa.Column("extraction_run_id", sa.String(length=64), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_teams", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("eligible_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ineligible_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("needs_review_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("run_id", name="pk_eligibility_runs"),
        sa.ForeignKeyConstraint(
            ["config_id", "config_version"],
            ["rule_configurations.config_id", "rule_configurations.version"],
            name="fk_elig_runs_config",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.dataset_id"], name="fk_elig_runs_dataset", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["extraction_run_id"], ["extraction_runs.run_id"], name="fk_elig_runs_extraction", ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_elig_runs_config",
        "eligibility_runs",
        ["config_id", "config_version"],
    )
    op.create_index(
        "ix_elig_runs_dataset",
        "eligibility_runs",
        ["dataset_id"],
    )
    op.create_index(
        "ix_elig_runs_extraction",
        "eligibility_runs",
        ["extraction_run_id"],
    )
    op.create_index(
        "ix_elig_runs_evaluated",
        "eligibility_runs",
        [sa.text("evaluated_at DESC")],
    )

    # 6. manual_overrides
    op.create_table(
        "manual_overrides",
        sa.Column("override_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("team_id", sa.String(length=64), nullable=False),
        sa.Column("original_status", sa.String(length=32), nullable=False),
        sa.Column("override_status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("overridden_by", sa.String(length=128), nullable=False, server_default="organizer"),
        sa.Column("overridden_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("override_id", name="pk_manual_overrides"),
        sa.ForeignKeyConstraint(["run_id"], ["eligibility_runs.run_id"], name="fk_manual_overrides_run", ondelete="CASCADE"),
        sa.UniqueConstraint("run_id", "team_id", name="uq_manual_overrides_run_team"),
    )
    op.create_index(
        "ix_manual_overrides_run",
        "manual_overrides",
        ["run_id"],
    )
    op.create_index(
        "ix_manual_overrides_team",
        "manual_overrides",
        ["run_id", "team_id"],
    )

    # 7. scoring_runs
    op.create_table(
        "scoring_runs",
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("config_id", sa.String(length=64), nullable=False),
        sa.Column("config_version", sa.Integer(), nullable=False),
        sa.Column("config_source", sa.String(length=16), nullable=False, server_default="stored"),
        sa.Column("eligibility_run_id", sa.String(length=64), nullable=True),
        sa.Column("dataset_id", sa.String(length=64), nullable=True),
        sa.Column("extraction_run_id", sa.String(length=64), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_teams", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("calculated_teams", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("average_score", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("run_id", name="pk_scoring_runs"),
        sa.ForeignKeyConstraint(["eligibility_run_id"], ["eligibility_runs.run_id"], name="fk_scoring_runs_elig", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.dataset_id"], name="fk_scoring_runs_dataset", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["extraction_run_id"], ["extraction_runs.run_id"], name="fk_scoring_runs_extraction", ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_scoring_runs_config",
        "scoring_runs",
        ["config_id", "config_version"],
    )
    op.create_index(
        "ix_scoring_runs_elig",
        "scoring_runs",
        ["eligibility_run_id"],
    )
    op.create_index(
        "ix_scoring_runs_dataset",
        "scoring_runs",
        ["dataset_id"],
    )
    op.create_index(
        "ix_scoring_runs_extraction",
        "scoring_runs",
        ["extraction_run_id"],
    )
    op.create_index(
        "ix_scoring_runs_evaluated",
        "scoring_runs",
        [sa.text("evaluated_at DESC")],
    )

    # 8. ranking_runs
    op.create_table(
        "ranking_runs",
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("scoring_run_id", sa.String(length=64), nullable=True),
        sa.Column("eligibility_run_id", sa.String(length=64), nullable=True),
        sa.Column("dataset_id", sa.String(length=64), nullable=True),
        sa.Column("extraction_run_id", sa.String(length=64), nullable=True),
        sa.Column("top_x", sa.Integer(), nullable=False),
        sa.Column("include_needs_review", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("tiebreak_criterion_id", sa.String(length=64), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("selected_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("shortage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cutoff_score", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("run_id", name="pk_ranking_runs"),
        sa.ForeignKeyConstraint(["scoring_run_id"], ["scoring_runs.run_id"], name="fk_ranking_runs_scoring", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["eligibility_run_id"], ["eligibility_runs.run_id"], name="fk_ranking_runs_elig", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.dataset_id"], name="fk_ranking_runs_dataset", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["extraction_run_id"], ["extraction_runs.run_id"], name="fk_ranking_runs_extraction", ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_ranking_runs_scoring",
        "ranking_runs",
        ["scoring_run_id"],
    )
    op.create_index(
        "ix_ranking_runs_elig",
        "ranking_runs",
        ["eligibility_run_id"],
    )
    op.create_index(
        "ix_ranking_runs_dataset",
        "ranking_runs",
        ["dataset_id"],
    )
    op.create_index(
        "ix_ranking_runs_extraction",
        "ranking_runs",
        ["extraction_run_id"],
    )
    op.create_index(
        "ix_ranking_runs_evaluated",
        "ranking_runs",
        [sa.text("evaluated_at DESC")],
    )


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.drop_table("ranking_runs")
    op.drop_table("scoring_runs")
    op.drop_table("manual_overrides")
    op.drop_table("eligibility_runs")
    op.drop_table("extraction_runs")
    op.drop_table("datasets")
    op.drop_table("scoring_configurations")
    op.drop_table("rule_configurations")
