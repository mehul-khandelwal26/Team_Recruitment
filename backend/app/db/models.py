"""SQLAlchemy ORM models and payload-to-columns derivation helpers.

Architectural Guarantees:
- Hybrid Relational-JSONB architecture: The JSONB `payload` column is the source of truth.
- Typed columns are derived from the payload to support relational lookups, constraints, and indexes.
- Explicit payload-to-columns helper per table guarantees consistency during inserts/updates.
- Provenance foreign keys enforce ON DELETE RESTRICT to protect historical evaluation integrity.
- Manual overrides enforce ON DELETE CASCADE from eligibility runs and UNIQUE (run_id, team_id).
- Future payload updates (e.g. soft deletes) must update derived columns in the same transaction.
"""

from __future__ import annotations

import datetime
from typing import Any, Optional

from pydantic import BaseModel
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


# ---------------------------------------------------------------------------
# Utility helpers for derivation
# ---------------------------------------------------------------------------


def _to_dict(obj: Any) -> dict[str, Any]:
    """Convert a Pydantic model or dict to a pure dictionary."""
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, dict):
        return dict(obj)
    raise TypeError(f"Expected dict or BaseModel, got {type(obj)}")


def _parse_dt(val: Any) -> datetime.datetime | None:
    """Parse an ISO datetime string or datetime object into a timezone-aware datetime."""
    if val is None:
        return None
    if isinstance(val, datetime.datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=datetime.timezone.utc)
        return val
    if isinstance(val, str):
        cleaned = val.strip()
        if not cleaned:
            return None
        if cleaned.endswith("Z") or cleaned.endswith("z"):
            cleaned = cleaned[:-1] + "+00:00"
        try:
            dt = datetime.datetime.fromisoformat(cleaned)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt
        except Exception:
            return None
    return None


def _now_utc() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


# ---------------------------------------------------------------------------
# 1. Rule Configurations
# ---------------------------------------------------------------------------


class RuleConfigurationModel(Base):
    """Versioned, immutable eligibility configurations.

    Expected payload structure:
    `app.rules.schemas.RuleConfiguration` containing:
    - config_id: str
    - version: int
    - name: str
    - description: str
    - global_config: dict / GlobalRuleConfig
    - rules: list[RuleDefinition]
    - is_active: bool
    - created_at: str (ISO)
    - updated_at: str (ISO)

    All future updates (such as soft delete marking is_active=False) must update
    both the payload and derived columns in the same transaction.
    """

    __tablename__ = "rule_configurations"

    config_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        Index("ix_rule_configs_active", "config_id", "is_active"),
        Index("ix_rule_configs_version", "config_id", version.desc()),
    )


def derive_rule_configuration_columns(
    payload: dict[str, Any] | BaseModel,
) -> dict[str, Any]:
    """Derive typed columns for `rule_configurations` from its source-of-truth payload."""
    data = _to_dict(payload)
    now = _now_utc()

    config_id = data.get("config_id")
    if not config_id:
        raise ValueError("RuleConfiguration payload must contain 'config_id'.")

    version = int(data.get("version", 1))
    name = str(data.get("name") or "")
    description = data.get("description")
    is_active = bool(data.get("is_active", True))

    created_at = _parse_dt(data.get("created_at")) or now
    updated_at = _parse_dt(data.get("updated_at")) or now

    return {
        "config_id": config_id,
        "version": version,
        "name": name,
        "description": description,
        "is_active": is_active,
        "created_at": created_at,
        "updated_at": updated_at,
        "payload": data,
    }


# ---------------------------------------------------------------------------
# 2. Datasets
# ---------------------------------------------------------------------------


class DatasetModel(Base):
    """Identifiable uploaded team-data snapshots supporting upload-once workflows.

    Expected payload structure:
    `app.schemas.ingestion.UploadResponse` containing:
    - success: bool
    - teams_count: int
    - members_count: int
    - teams: list[TeamSchema]
    - warnings: list[ValidationWarning]
    - errors: list[ValidationError]
    - unmapped_fields: list[str]

    Metadata not stored in UploadResponse (filename, file_type, mapping) must be
    supplied explicitly via derive_dataset_columns parameters.
    """

    __tablename__ = "datasets"

    dataset_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(16), nullable=False)
    teams_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    members_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    uploaded_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    mapping: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    warnings: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    unmapped_fields: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (Index("ix_datasets_uploaded", uploaded_at.desc()),)


def derive_dataset_columns(
    payload: dict[str, Any] | BaseModel,
    *,
    dataset_id: str,
    filename: str,
    file_type: str,
    uploaded_at: str | datetime.datetime | None = None,
    mapping: dict[str, Any] | None = None,
    teams_count: int | None = None,
    members_count: int | None = None,
    warnings: list[Any] | None = None,
    unmapped_fields: list[Any] | None = None,
) -> dict[str, Any]:
    """Derive typed columns for `datasets` from payload and explicit file metadata.

    Filename, file_type, dataset_id, and mapping are upload metadata not held in
    UploadResponse; they must be provided as explicit arguments.
    """
    data = _to_dict(payload)
    now = _now_utc()

    if not dataset_id:
        raise ValueError("dataset_id is required for dataset persistence.")
    if not filename:
        raise ValueError("filename is required for dataset persistence.")
    if not file_type:
        raise ValueError("file_type is required for dataset persistence.")

    parsed_uploaded = _parse_dt(uploaded_at) or now
    if teams_count is not None:
        effective_teams_count = int(teams_count)
    else:
        effective_teams_count = int(data.get("teams_count", len(data.get("teams", []))))

    if members_count is not None:
        effective_members_count = int(members_count)
    else:
        effective_members_count = int(data.get("members_count", 0))

    effective_warnings = warnings if warnings is not None else data.get("warnings", [])
    effective_unmapped = unmapped_fields if unmapped_fields is not None else data.get("unmapped_fields", [])

    return {
        "dataset_id": dataset_id,
        "filename": filename,
        "file_type": file_type.lower(),
        "teams_count": effective_teams_count,
        "members_count": effective_members_count,
        "uploaded_at": parsed_uploaded,
        "mapping": mapping,
        "warnings": effective_warnings,
        "unmapped_fields": effective_unmapped,
        "payload": data,
    }


# ---------------------------------------------------------------------------
# 3. Extraction Runs
# ---------------------------------------------------------------------------


class ExtractionRunModel(Base):
    """Stored signal extraction outputs.

    Expected payload structure:
    `app.signals.schemas.ExtractionRunResponse` containing:
    - run_id: str
    - teams: list[TeamExtractionResult]
    - selected_signals: list[str]
    - analyzers_executed: list[str]
    - total_teams: int
    - total_members: int
    - warnings: list[str]
    - errors: list[str]
    - dataset_id: Optional[str]
    - created_at: Optional[str]
    """

    __tablename__ = "extraction_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dataset_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("datasets.dataset_id", ondelete="RESTRICT"),
        nullable=True,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    selected_signals: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    analyzers_executed: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    total_teams: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_members: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        Index("ix_extraction_runs_dataset", "dataset_id"),
        Index("ix_extraction_runs_created", created_at.desc()),
    )


def derive_extraction_run_columns(
    payload: dict[str, Any] | BaseModel,
) -> dict[str, Any]:
    """Derive typed columns for `extraction_runs` from its source-of-truth payload."""
    data = _to_dict(payload)
    now = _now_utc()

    run_id = data.get("run_id")
    if not run_id:
        raise ValueError("ExtractionRun payload must contain 'run_id'.")

    dataset_id = data.get("dataset_id")
    created_at = _parse_dt(data.get("created_at")) or now
    selected_signals = data.get("selected_signals", [])
    analyzers_executed = data.get("analyzers_executed", [])
    total_teams = int(data.get("total_teams", len(data.get("teams", []))))
    total_members = int(data.get("total_members", 0))

    return {
        "run_id": run_id,
        "dataset_id": dataset_id,
        "created_at": created_at,
        "selected_signals": selected_signals,
        "analyzers_executed": analyzers_executed,
        "total_teams": total_teams,
        "total_members": total_members,
        "payload": data,
    }


# ---------------------------------------------------------------------------
# 4. Eligibility Runs
# ---------------------------------------------------------------------------


class EligibilityRunModel(Base):
    """Historical record of eligibility evaluation decisions.

    Expected payload structure:
    `app.rules.schemas.EligibilityRunResponse` containing:
    - run_id: str
    - config_id: str
    - config_version: int
    - evaluated_at: str (ISO)
    - teams: list[TeamEligibilityResult]
    - summary: EligibilityRunSummary (total_teams, eligible_count, ineligible_count, needs_review_count)
    - warnings: list[str]
    - errors: list[str]
    - dataset_id: Optional[str]
    - extraction_run_id: Optional[str]

    Composite FK (config_id, config_version) ensures eligibility runs reference valid stored configs.
    """

    __tablename__ = "eligibility_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    config_id: Mapped[str] = mapped_column(String(64), nullable=False)
    config_version: Mapped[int] = mapped_column(Integer, nullable=False)
    dataset_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("datasets.dataset_id", ondelete="RESTRICT"),
        nullable=True,
    )
    extraction_run_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("extraction_runs.run_id", ondelete="RESTRICT"),
        nullable=True,
    )
    evaluated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    total_teams: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    eligible_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ineligible_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    needs_review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["config_id", "config_version"],
            ["rule_configurations.config_id", "rule_configurations.version"],
            ondelete="RESTRICT",
        ),
        Index("ix_elig_runs_config", "config_id", "config_version"),
        Index("ix_elig_runs_dataset", "dataset_id"),
        Index("ix_elig_runs_extraction", "extraction_run_id"),
        Index("ix_elig_runs_evaluated", evaluated_at.desc()),
    )


def derive_eligibility_run_columns(
    payload: dict[str, Any] | BaseModel,
) -> dict[str, Any]:
    """Derive typed columns for `eligibility_runs` from its source-of-truth payload."""
    data = _to_dict(payload)
    now = _now_utc()

    run_id = data.get("run_id")
    if not run_id:
        raise ValueError("EligibilityRun payload must contain 'run_id'.")

    config_id = data.get("config_id")
    if not config_id:
        raise ValueError("EligibilityRun payload must contain 'config_id'.")

    config_version = int(data.get("config_version", 1))
    dataset_id = data.get("dataset_id")
    extraction_run_id = data.get("extraction_run_id")
    evaluated_at = _parse_dt(data.get("evaluated_at")) or now

    summary = data.get("summary") or {}
    total_teams = int(summary.get("total_teams", len(data.get("teams", []))))
    eligible_count = int(summary.get("eligible_count", 0))
    ineligible_count = int(summary.get("ineligible_count", 0))
    needs_review_count = int(summary.get("needs_review_count", 0))

    return {
        "run_id": run_id,
        "config_id": config_id,
        "config_version": config_version,
        "dataset_id": dataset_id,
        "extraction_run_id": extraction_run_id,
        "evaluated_at": evaluated_at,
        "total_teams": total_teams,
        "eligible_count": eligible_count,
        "ineligible_count": ineligible_count,
        "needs_review_count": needs_review_count,
        "payload": data,
    }


# ---------------------------------------------------------------------------
# 5. Manual Overrides
# ---------------------------------------------------------------------------


class ManualOverrideModel(Base):
    """Audit log of organizer manual overrides for eligibility decisions.

    Expected payload structure:
    `app.rules.schemas.ManualOverride` containing:
    - override_id: str
    - run_id: str
    - team_id: str
    - original_status: str / EligibilityStatus
    - override_status: str / EligibilityStatus
    - reason: str
    - overridden_by: str
    - overridden_at: str (ISO)

    UniqueConstraint on (run_id, team_id) enforces current-only override semantics:
    an existing team override within a run is replaced without creating history.
    """

    __tablename__ = "manual_overrides"

    override_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("eligibility_runs.run_id", ondelete="CASCADE"),
        nullable=False,
    )
    team_id: Mapped[str] = mapped_column(String(64), nullable=False)
    original_status: Mapped[str] = mapped_column(String(32), nullable=False)
    override_status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    overridden_by: Mapped[str] = mapped_column(
        String(128), nullable=False, default="organizer"
    )
    overridden_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        UniqueConstraint("run_id", "team_id", name="uq_manual_overrides_run_team"),
        Index("ix_manual_overrides_run", "run_id"),
        Index("ix_manual_overrides_team", "run_id", "team_id"),
    )


def derive_manual_override_columns(
    payload: dict[str, Any] | BaseModel,
) -> dict[str, Any]:
    """Derive typed columns for `manual_overrides` from its source-of-truth payload."""
    data = _to_dict(payload)
    now = _now_utc()

    override_id = data.get("override_id")
    if not override_id:
        raise ValueError("ManualOverride payload must contain 'override_id'.")

    run_id = data.get("run_id")
    if not run_id:
        raise ValueError("ManualOverride payload must contain 'run_id'.")

    team_id = data.get("team_id")
    if not team_id:
        raise ValueError("ManualOverride payload must contain 'team_id'.")

    original_status = str(data.get("original_status") or "")
    override_status = str(data.get("override_status") or "")
    reason = str(data.get("reason") or "")
    overridden_by = str(data.get("overridden_by") or "organizer")
    overridden_at = _parse_dt(data.get("overridden_at")) or now

    return {
        "override_id": override_id,
        "run_id": run_id,
        "team_id": team_id,
        "original_status": original_status,
        "override_status": override_status,
        "reason": reason,
        "overridden_by": overridden_by,
        "overridden_at": overridden_at,
        "payload": data,
    }


# ---------------------------------------------------------------------------
# 6. Scoring Configurations
# ---------------------------------------------------------------------------


class ScoringConfigurationModel(Base):
    """Versioned, immutable scoring rubrics and weighting configurations.

    Expected payload structure:
    `app.scoring.schemas.ScoringConfiguration` containing:
    - config_id: str
    - name: str
    - version: int
    - description: Optional[str]
    - criteria: list[EvaluationCriterion]
    - scale_max: float
    - lead_field: Optional[str]
    - lead_values: list[str]
    - score_ineligible_teams: bool
    - is_active: bool
    - created_at: Optional[str]
    - updated_at: Optional[str]
    """

    __tablename__ = "scoring_configurations"

    config_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scale_max: Mapped[float] = mapped_column(
        Numeric(6, 2), nullable=False, default=100.0
    )
    score_ineligible_teams: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        Index("ix_scoring_configs_active", "config_id", "is_active"),
        Index("ix_scoring_configs_version", "config_id", version.desc()),
    )


def derive_scoring_configuration_columns(
    payload: dict[str, Any] | BaseModel,
) -> dict[str, Any]:
    """Derive typed columns for `scoring_configurations` from its source-of-truth payload."""
    data = _to_dict(payload)
    now = _now_utc()

    config_id = data.get("config_id")
    if not config_id:
        raise ValueError("ScoringConfiguration payload must contain 'config_id'.")

    version = int(data.get("version", 1))
    name = str(data.get("name") or "")
    description = data.get("description")
    scale_max = float(data.get("scale_max", 100.0))
    score_ineligible_teams = bool(data.get("score_ineligible_teams", True))
    is_active = bool(data.get("is_active", True))

    created_at = _parse_dt(data.get("created_at")) or now
    updated_at = _parse_dt(data.get("updated_at")) or now

    return {
        "config_id": config_id,
        "version": version,
        "name": name,
        "description": description,
        "scale_max": scale_max,
        "score_ineligible_teams": score_ineligible_teams,
        "is_active": is_active,
        "created_at": created_at,
        "updated_at": updated_at,
        "payload": data,
    }


# ---------------------------------------------------------------------------
# 7. Scoring Runs
# ---------------------------------------------------------------------------


class ScoringRunModel(Base):
    """Historical records of weighted scoring runs and criteria breakdowns.

    Expected payload structure:
    `app.scoring.schemas.ScoringRunResponse` containing:
    - run_id: str
    - config_id: str
    - config_version: int
    - evaluated_at: str (ISO)
    - teams: list[TeamScoringResult]
    - summary: ScoringRunSummary
    - warnings: list[str]
    - errors: list[str]
    - eligibility_run_id: Optional[str]
    - dataset_id: Optional[str]
    - extraction_run_id: Optional[str]
    - config_source: Optional[str] ('stored' or 'inline')
    - config_snapshot: Optional[ScoringConfiguration]

    Scoring accepts inline configs, so there is NO foreign key to scoring_configurations.
    """

    __tablename__ = "scoring_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    config_id: Mapped[str] = mapped_column(String(64), nullable=False)
    config_version: Mapped[int] = mapped_column(Integer, nullable=False)
    config_source: Mapped[str] = mapped_column(
        String(16), nullable=False, default="stored"
    )
    eligibility_run_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("eligibility_runs.run_id", ondelete="RESTRICT"),
        nullable=True,
    )
    dataset_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("datasets.dataset_id", ondelete="RESTRICT"),
        nullable=True,
    )
    extraction_run_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("extraction_runs.run_id", ondelete="RESTRICT"),
        nullable=True,
    )
    evaluated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    total_teams: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    calculated_teams: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    average_score: Mapped[Optional[float]] = mapped_column(
        Numeric(6, 2), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        Index("ix_scoring_runs_config", "config_id", "config_version"),
        Index("ix_scoring_runs_elig", "eligibility_run_id"),
        Index("ix_scoring_runs_dataset", "dataset_id"),
        Index("ix_scoring_runs_extraction", "extraction_run_id"),
        Index("ix_scoring_runs_evaluated", evaluated_at.desc()),
    )


def derive_scoring_run_columns(
    payload: dict[str, Any] | BaseModel,
) -> dict[str, Any]:
    """Derive typed columns for `scoring_runs` from its source-of-truth payload."""
    data = _to_dict(payload)
    now = _now_utc()

    run_id = data.get("run_id")
    if not run_id:
        raise ValueError("ScoringRun payload must contain 'run_id'.")

    config_id = data.get("config_id")
    if not config_id:
        raise ValueError("ScoringRun payload must contain 'config_id'.")

    config_version = int(data.get("config_version", 1))
    config_source = str(data.get("config_source") or "stored")
    eligibility_run_id = data.get("eligibility_run_id")
    dataset_id = data.get("dataset_id")
    extraction_run_id = data.get("extraction_run_id")
    evaluated_at = _parse_dt(data.get("evaluated_at")) or now

    summary = data.get("summary") or {}
    total_teams = int(summary.get("total_teams", len(data.get("teams", []))))
    calculated_teams = int(summary.get("calculated_teams", 0))
    avg_score = summary.get("average_score")
    average_score = float(avg_score) if avg_score is not None else None

    return {
        "run_id": run_id,
        "config_id": config_id,
        "config_version": config_version,
        "config_source": config_source,
        "eligibility_run_id": eligibility_run_id,
        "dataset_id": dataset_id,
        "extraction_run_id": extraction_run_id,
        "evaluated_at": evaluated_at,
        "total_teams": total_teams,
        "calculated_teams": calculated_teams,
        "average_score": average_score,
        "payload": data,
    }


# ---------------------------------------------------------------------------
# 8. Ranking Runs
# ---------------------------------------------------------------------------


class RankingRunModel(Base):
    """Historical Top-X selection and deterministic ranking results.

    Expected payload structure:
    `app.ranking.schemas.RankingRunResponse` containing:
    - run_id: str
    - scoring_run_id: Optional[str]
    - eligibility_run_id: Optional[str]
    - evaluated_at: str (ISO)
    - top_x: int
    - include_needs_review: bool
    - tiebreak_criterion_id: Optional[str]
    - selected_teams: list[RankedTeamResult]
    - ranked_teams: list[RankedTeamResult]
    - needs_review_teams: list[RankedTeamResult]
    - recommended_review_candidates: list[RankedTeamResult]
    - unresolved_teams: list[ExcludedTeamResult]
    - excluded_teams: list[ExcludedTeamResult]
    - summary: RankingRunSummary
    - warnings: list[str]
    - errors: list[str]
    - dataset_id: Optional[str]
    - extraction_run_id: Optional[str]
    """

    __tablename__ = "ranking_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    scoring_run_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("scoring_runs.run_id", ondelete="RESTRICT"),
        nullable=True,
    )
    eligibility_run_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("eligibility_runs.run_id", ondelete="RESTRICT"),
        nullable=True,
    )
    dataset_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("datasets.dataset_id", ondelete="RESTRICT"),
        nullable=True,
    )
    extraction_run_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("extraction_runs.run_id", ondelete="RESTRICT"),
        nullable=True,
    )
    top_x: Mapped[int] = mapped_column(Integer, nullable=False)
    include_needs_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    tiebreak_criterion_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )
    evaluated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    selected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shortage: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cutoff_score: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        Index("ix_ranking_runs_scoring", "scoring_run_id"),
        Index("ix_ranking_runs_elig", "eligibility_run_id"),
        Index("ix_ranking_runs_dataset", "dataset_id"),
        Index("ix_ranking_runs_extraction", "extraction_run_id"),
        Index("ix_ranking_runs_evaluated", evaluated_at.desc()),
    )


def derive_ranking_run_columns(
    payload: dict[str, Any] | BaseModel,
) -> dict[str, Any]:
    """Derive typed columns for `ranking_runs` from its source-of-truth payload."""
    data = _to_dict(payload)
    now = _now_utc()

    run_id = data.get("run_id")
    if not run_id:
        raise ValueError("RankingRun payload must contain 'run_id'.")

    scoring_run_id = data.get("scoring_run_id")
    eligibility_run_id = data.get("eligibility_run_id")
    dataset_id = data.get("dataset_id")
    extraction_run_id = data.get("extraction_run_id")

    top_x = int(data.get("top_x", 0))
    include_needs_review = bool(data.get("include_needs_review", False))
    tiebreak_criterion_id = data.get("tiebreak_criterion_id")
    evaluated_at = _parse_dt(data.get("evaluated_at")) or now

    summary = data.get("summary") or {}
    selected_count = int(
        summary.get("selected_teams_count", len(data.get("selected_teams", [])))
    )
    shortage = int(summary.get("shortage", 0))
    cutoff_val = summary.get("cutoff_score")
    cutoff_score = float(cutoff_val) if cutoff_val is not None else None

    return {
        "run_id": run_id,
        "scoring_run_id": scoring_run_id,
        "eligibility_run_id": eligibility_run_id,
        "dataset_id": dataset_id,
        "extraction_run_id": extraction_run_id,
        "top_x": top_x,
        "include_needs_review": include_needs_review,
        "tiebreak_criterion_id": tiebreak_criterion_id,
        "evaluated_at": evaluated_at,
        "selected_count": selected_count,
        "shortage": shortage,
        "cutoff_score": cutoff_score,
        "payload": data,
    }
