"""PostgreSQL-backed store implementations for recruitment evaluation entities.

Provides PostgreSQL persistence for:
1. PostgresRuleConfigStore: versioned rule configurations with transactional soft delete.
2. PostgresScoringConfigStore: versioned scoring configurations with criteria and weightings.
3. PostgresEligibilityRunStore: evaluation run history respecting foreign keys.
4. PostgresManualOverrideStore: atomic ON CONFLICT DO UPDATE upsert on (run_id, team_id).
5. PostgresScoringRunStore: historical scoring runs with criteria breakdowns and snapshots.
6. PostgresRankingRunStore: Top-X shortlisted rankings and exclusion audits.

Invariants:
- All stores accept an optional injected Engine; if injected, that engine is strictly used.
- Stores lazily initialize connections only when entering transactional sessions.
- No database connections are made at module import time.
- JSONB payloads remain source of truth; derived typed columns support constraints and indexing.
"""

from __future__ import annotations

from contextlib import contextmanager
import datetime
from typing import TYPE_CHECKING, Any, Generator, Optional

import sqlalchemy as sa
from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    DatasetModel,
    EligibilityRunModel,
    ExtractionRunModel,
    ManualOverrideModel,
    RankingRunModel,
    RuleConfigurationModel,
    ScoringConfigurationModel,
    ScoringRunModel,
    derive_dataset_columns,
    derive_eligibility_run_columns,
    derive_extraction_run_columns,
    derive_manual_override_columns,
    derive_ranking_run_columns,
    derive_rule_configuration_columns,
    derive_scoring_configuration_columns,
    derive_scoring_run_columns,
)
from app.db.session import get_session_factory, session_scope

if TYPE_CHECKING:
    from app.ranking.schemas import RankingRunResponse
    from app.rules.schemas import (
        EligibilityRunResponse,
        ManualOverride,
        RuleConfiguration,
        RuleConfigurationUpdate,
    )
    from app.schemas.ingestion import DatasetRecord
    from app.scoring.schemas import (
        ScoringConfiguration,
        ScoringConfigurationUpdate,
        ScoringRunResponse,
    )
    from app.signals.schemas import ExtractionRunResponse


class BasePostgresStore:
    """Base class providing injected engine support and lazy session management."""

    def __init__(self, engine: Optional[Engine] = None) -> None:
        self._engine: Optional[Engine] = engine
        self._session_factory: Optional[sessionmaker[Session]] = (
            get_session_factory(engine) if engine is not None else None
        )

    @property
    def engine(self) -> Optional[Engine]:
        return self._engine

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """Provide a transactional session scope using the injected or default engine."""
        if self._session_factory is None:
            self._session_factory = get_session_factory(self._engine)
        with session_scope(self._session_factory) as s:
            yield s

    def _assert_safe_reset(self) -> None:
        """Resolve effective engine and verify it targets a safe test database before reset.

        Raises:
            ValueError: If the engine targets a non-test database or unsafe configuration.
                        Never includes the database URL or credentials in the error message.
        """
        from app.config import assert_safe_test_database
        from app.db.session import create_app_engine

        try:
            target_engine = self._engine or create_app_engine()
        except RuntimeError:
            raise ValueError("Safety check failed: Unable to resolve database engine for reset.") from None

        url_str = target_engine.url.render_as_string(hide_password=False)
        assert_safe_test_database(url_str)



# ---------------------------------------------------------------------------
# 1. Rule Configuration Store
# ---------------------------------------------------------------------------


class PostgresRuleConfigStore(BasePostgresStore):
    """PostgreSQL store for versioned eligibility rule configurations."""

    def get(self, config_id: str, version: Optional[int] = None) -> Optional[RuleConfiguration]:
        from app.rules.schemas import RuleConfiguration

        with self.session() as s:
            if version is not None:
                stmt = select(RuleConfigurationModel).where(
                    RuleConfigurationModel.config_id == config_id,
                    RuleConfigurationModel.version == version,
                )
            else:
                stmt = (
                    select(RuleConfigurationModel)
                    .where(RuleConfigurationModel.config_id == config_id)
                    .order_by(RuleConfigurationModel.version.desc())
                    .limit(1)
                )
            row = s.execute(stmt).scalars().first()
            if row is None:
                return None
            cfg = RuleConfiguration.model_validate(row.payload)
            cfg.is_active = row.is_active
            return cfg

    def list_latest(self) -> list[RuleConfiguration]:
        from app.rules.schemas import RuleConfiguration

        with self.session() as s:
            subq = (
                select(
                    RuleConfigurationModel.config_id,
                    func.max(RuleConfigurationModel.version).label("max_v"),
                )
                .group_by(RuleConfigurationModel.config_id)
                .subquery()
            )
            stmt = (
                select(RuleConfigurationModel)
                .join(
                    subq,
                    and_(
                        RuleConfigurationModel.config_id == subq.c.config_id,
                        RuleConfigurationModel.version == subq.c.max_v,
                    ),
                )
                .where(RuleConfigurationModel.is_active.is_(True))
                .order_by(RuleConfigurationModel.config_id)
            )
            rows = s.execute(stmt).scalars().all()
            results = []
            for r in rows:
                cfg = RuleConfiguration.model_validate(r.payload)
                cfg.is_active = r.is_active
                results.append(cfg)
            return results

    def list_versions(self, config_id: str) -> list[int]:
        with self.session() as s:
            stmt = (
                select(RuleConfigurationModel.version)
                .where(RuleConfigurationModel.config_id == config_id)
                .order_by(RuleConfigurationModel.version.asc())
            )
            return list(s.execute(stmt).scalars().all())

    def save(self, config: RuleConfiguration) -> RuleConfiguration:
        now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if not config.created_at:
            config.created_at = now_ts
        config.updated_at = now_ts

        derived = derive_rule_configuration_columns(config)
        with self.session() as s:
            model = RuleConfigurationModel(**derived)
            s.add(model)
        return config

    def update(
        self, config_id: str, update_payload: RuleConfigurationUpdate
    ) -> Optional[RuleConfiguration]:
        from app.rules.schemas import RuleConfiguration

        current = self.get(config_id)
        if current is None:
            return None

        new_version = current.version + 1
        now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

        new_config = RuleConfiguration(
            config_id=config_id,
            version=new_version,
            name=update_payload.name if update_payload.name is not None else current.name,
            description=(
                update_payload.description
                if update_payload.description is not None
                else current.description
            ),
            global_config=(
                update_payload.global_config
                if update_payload.global_config is not None
                else current.global_config.model_copy(deep=True)
            ),
            rules=[
                r.model_copy(deep=True)
                for r in (
                    update_payload.rules
                    if update_payload.rules is not None
                    else current.rules
                )
            ],
            is_active=(
                update_payload.is_active
                if update_payload.is_active is not None
                else current.is_active
            ),
            created_at=current.created_at,
            updated_at=now_ts,
        )
        return self.save(new_config)

    def delete(self, config_id: str) -> bool:
        """Soft-delete all versions of the given configuration in a single transaction."""
        with self.session() as s:
            stmt = select(RuleConfigurationModel).where(
                RuleConfigurationModel.config_id == config_id
            )
            rows = s.execute(stmt).scalars().all()
            if not rows:
                return False

            for row in rows:
                row.is_active = False
                payload_dict = dict(row.payload)
                payload_dict["is_active"] = False
                row.payload = payload_dict
            return True

    def reset(self) -> None:
        """Test isolation helper: clears all rule configurations."""
        self._assert_safe_reset()
        with self.session() as s:
            s.execute(sa.text("DELETE FROM rule_configurations;"))


# ---------------------------------------------------------------------------
# 2. Scoring Configuration Store
# ---------------------------------------------------------------------------


class PostgresScoringConfigStore(BasePostgresStore):
    """PostgreSQL store for versioned scoring rubrics and weighting configurations."""

    def get(self, config_id: str, version: Optional[int] = None) -> Optional[ScoringConfiguration]:
        from app.scoring.schemas import ScoringConfiguration

        with self.session() as s:
            if version is not None:
                stmt = select(ScoringConfigurationModel).where(
                    ScoringConfigurationModel.config_id == config_id,
                    ScoringConfigurationModel.version == version,
                )
            else:
                stmt = (
                    select(ScoringConfigurationModel)
                    .where(ScoringConfigurationModel.config_id == config_id)
                    .order_by(ScoringConfigurationModel.version.desc())
                    .limit(1)
                )
            row = s.execute(stmt).scalars().first()
            if row is None:
                return None
            cfg = ScoringConfiguration.model_validate(row.payload)
            cfg.is_active = row.is_active
            return cfg

    def list_latest(self) -> list[ScoringConfiguration]:
        from app.scoring.schemas import ScoringConfiguration

        with self.session() as s:
            subq = (
                select(
                    ScoringConfigurationModel.config_id,
                    func.max(ScoringConfigurationModel.version).label("max_v"),
                )
                .group_by(ScoringConfigurationModel.config_id)
                .subquery()
            )
            stmt = (
                select(ScoringConfigurationModel)
                .join(
                    subq,
                    and_(
                        ScoringConfigurationModel.config_id == subq.c.config_id,
                        ScoringConfigurationModel.version == subq.c.max_v,
                    ),
                )
                .where(ScoringConfigurationModel.is_active.is_(True))
                .order_by(ScoringConfigurationModel.config_id)
            )
            rows = s.execute(stmt).scalars().all()
            results = []
            for r in rows:
                cfg = ScoringConfiguration.model_validate(r.payload)
                cfg.is_active = r.is_active
                results.append(cfg)
            return results

    def list_versions(self, config_id: str) -> list[int]:
        with self.session() as s:
            stmt = (
                select(ScoringConfigurationModel.version)
                .where(ScoringConfigurationModel.config_id == config_id)
                .order_by(ScoringConfigurationModel.version.asc())
            )
            return list(s.execute(stmt).scalars().all())

    def save(self, config: ScoringConfiguration) -> ScoringConfiguration:
        now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if not config.created_at:
            config.created_at = now_ts
        config.updated_at = now_ts

        derived = derive_scoring_configuration_columns(config)
        with self.session() as s:
            model = ScoringConfigurationModel(**derived)
            s.add(model)
        return config

    def update(
        self, config_id: str, update_payload: ScoringConfigurationUpdate
    ) -> Optional[ScoringConfiguration]:
        from app.scoring.schemas import ScoringConfiguration

        current = self.get(config_id)
        if current is None:
            return None

        new_version = current.version + 1
        now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

        new_config = ScoringConfiguration(
            config_id=config_id,
            version=new_version,
            name=update_payload.name if update_payload.name is not None else current.name,
            description=(
                update_payload.description
                if update_payload.description is not None
                else current.description
            ),
            criteria=[
                c.model_copy(deep=True)
                for c in (
                    update_payload.criteria
                    if update_payload.criteria is not None
                    else current.criteria
                )
            ],
            scale_max=(
                update_payload.scale_max
                if update_payload.scale_max is not None
                else current.scale_max
            ),
            lead_field=(
                update_payload.lead_field
                if update_payload.lead_field is not None
                else current.lead_field
            ),
            lead_values=(
                list(update_payload.lead_values)
                if update_payload.lead_values is not None
                else list(current.lead_values)
            ),
            score_ineligible_teams=(
                update_payload.score_ineligible_teams
                if update_payload.score_ineligible_teams is not None
                else current.score_ineligible_teams
            ),
            is_active=(
                update_payload.is_active
                if update_payload.is_active is not None
                else current.is_active
            ),
            created_at=current.created_at,
            updated_at=now_ts,
        )
        return self.save(new_config)

    def delete(self, config_id: str) -> bool:
        """Soft-delete all versions of the scoring configuration in a single transaction."""
        with self.session() as s:
            stmt = select(ScoringConfigurationModel).where(
                ScoringConfigurationModel.config_id == config_id
            )
            rows = s.execute(stmt).scalars().all()
            if not rows:
                return False

            for row in rows:
                row.is_active = False
                payload_dict = dict(row.payload)
                payload_dict["is_active"] = False
                row.payload = payload_dict
            return True

    def reset(self) -> None:
        """Test isolation helper: clears all scoring configurations."""
        self._assert_safe_reset()
        with self.session() as s:
            s.execute(sa.text("DELETE FROM scoring_configurations;"))


# ---------------------------------------------------------------------------
# 3. Eligibility Run Store
# ---------------------------------------------------------------------------


class PostgresEligibilityRunStore(BasePostgresStore):
    """PostgreSQL store for historical eligibility runs."""

    def save(self, record: EligibilityRunResponse) -> None:
        derived = derive_eligibility_run_columns(record)
        with self.session() as s:
            model = EligibilityRunModel(**derived)
            s.add(model)

    def get(self, run_id: str) -> Optional[EligibilityRunResponse]:
        from app.rules.schemas import EligibilityRunResponse

        with self.session() as s:
            stmt = select(EligibilityRunModel).where(EligibilityRunModel.run_id == run_id)
            row = s.execute(stmt).scalars().first()
            if row is None:
                return None
            return EligibilityRunResponse.model_validate(row.payload)

    def list_runs(self, config_id: Optional[str] = None) -> list[EligibilityRunResponse]:
        from app.rules.schemas import EligibilityRunResponse

        with self.session() as s:
            stmt = select(EligibilityRunModel)
            if config_id:
                stmt = stmt.where(EligibilityRunModel.config_id == config_id)
            stmt = stmt.order_by(EligibilityRunModel.evaluated_at.desc())
            rows = s.execute(stmt).scalars().all()
            return [EligibilityRunResponse.model_validate(r.payload) for r in rows]

    def delete(self, run_id: str) -> bool:
        """Delete eligibility run by run_id."""
        with self.session() as s:
            stmt = select(EligibilityRunModel).where(EligibilityRunModel.run_id == run_id)
            row = s.execute(stmt).scalars().first()
            if row is None:
                return False
            s.delete(row)
            return True

    def reset(self) -> None:
        """Test isolation helper: clears all eligibility runs."""
        self._assert_safe_reset()
        with self.session() as s:
            s.execute(sa.text("DELETE FROM eligibility_runs;"))


# ---------------------------------------------------------------------------
# 4. Manual Override Store
# ---------------------------------------------------------------------------


class PostgresManualOverrideStore(BasePostgresStore):
    """PostgreSQL store for manual eligibility overrides with atomic upsert."""

    def save(self, override: ManualOverride) -> None:
        derived = derive_manual_override_columns(override)
        stmt = pg_insert(ManualOverrideModel).values(**derived)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_manual_overrides_run_team",
            set_={
                "override_id": stmt.excluded.override_id,
                "original_status": stmt.excluded.original_status,
                "override_status": stmt.excluded.override_status,
                "reason": stmt.excluded.reason,
                "overridden_by": stmt.excluded.overridden_by,
                "overridden_at": stmt.excluded.overridden_at,
                "payload": stmt.excluded.payload,
            },
        )
        with self.session() as s:
            s.execute(stmt)

    def get_for_run(self, run_id: str) -> list[ManualOverride]:
        from app.rules.schemas import ManualOverride

        with self.session() as s:
            stmt = (
                select(ManualOverrideModel)
                .where(ManualOverrideModel.run_id == run_id)
                .order_by(ManualOverrideModel.overridden_at.asc())
            )
            rows = s.execute(stmt).scalars().all()
            return [ManualOverride.model_validate(r.payload) for r in rows]

    def get_for_team(self, run_id: str, team_id: str) -> Optional[ManualOverride]:
        from app.rules.schemas import ManualOverride

        with self.session() as s:
            stmt = (
                select(ManualOverrideModel)
                .where(
                    ManualOverrideModel.run_id == run_id,
                    ManualOverrideModel.team_id == team_id,
                )
                .limit(1)
            )
            row = s.execute(stmt).scalars().first()
            if row is None:
                return None
            return ManualOverride.model_validate(row.payload)

    def reset(self) -> None:
        """Test isolation helper: clears all manual overrides."""
        self._assert_safe_reset()
        with self.session() as s:
            s.execute(sa.text("DELETE FROM manual_overrides;"))


# ---------------------------------------------------------------------------
# 5. Scoring Run Store
# ---------------------------------------------------------------------------


class PostgresScoringRunStore(BasePostgresStore):
    """PostgreSQL store for historical scoring evaluation runs."""

    def save(self, record: ScoringRunResponse) -> None:
        derived = derive_scoring_run_columns(record)
        with self.session() as s:
            model = ScoringRunModel(**derived)
            s.add(model)

    def get(self, run_id: str) -> Optional[ScoringRunResponse]:
        from app.scoring.schemas import ScoringRunResponse

        with self.session() as s:
            stmt = select(ScoringRunModel).where(ScoringRunModel.run_id == run_id)
            row = s.execute(stmt).scalars().first()
            if row is None:
                return None
            return ScoringRunResponse.model_validate(row.payload)

    def list_runs(self, config_id: Optional[str] = None) -> list[ScoringRunResponse]:
        from app.scoring.schemas import ScoringRunResponse

        with self.session() as s:
            stmt = select(ScoringRunModel)
            if config_id:
                stmt = stmt.where(ScoringRunModel.config_id == config_id)
            stmt = stmt.order_by(ScoringRunModel.evaluated_at.desc())
            rows = s.execute(stmt).scalars().all()
            return [ScoringRunResponse.model_validate(r.payload) for r in rows]

    def delete(self, run_id: str) -> bool:
        """Delete scoring run by run_id."""
        with self.session() as s:
            stmt = select(ScoringRunModel).where(ScoringRunModel.run_id == run_id)
            row = s.execute(stmt).scalars().first()
            if row is None:
                return False
            s.delete(row)
            return True

    def reset(self) -> None:
        """Test isolation helper: clears all scoring runs."""
        self._assert_safe_reset()
        with self.session() as s:
            s.execute(sa.text("DELETE FROM scoring_runs;"))


# ---------------------------------------------------------------------------
# 6. Ranking Run Store
# ---------------------------------------------------------------------------


class PostgresRankingRunStore(BasePostgresStore):
    """PostgreSQL store for Top-X shortlisted rankings."""

    def save(self, record: RankingRunResponse) -> None:
        derived = derive_ranking_run_columns(record)
        with self.session() as s:
            model = RankingRunModel(**derived)
            s.add(model)

    def get(self, run_id: str) -> Optional[RankingRunResponse]:
        from app.ranking.schemas import RankingRunResponse

        with self.session() as s:
            stmt = select(RankingRunModel).where(RankingRunModel.run_id == run_id)
            row = s.execute(stmt).scalars().first()
            if row is None:
                return None
            return RankingRunResponse.model_validate(row.payload)

    def list_runs(self) -> list[RankingRunResponse]:
        from app.ranking.schemas import RankingRunResponse

        with self.session() as s:
            stmt = select(RankingRunModel).order_by(RankingRunModel.evaluated_at.desc())
            rows = s.execute(stmt).scalars().all()
            return [RankingRunResponse.model_validate(r.payload) for r in rows]

    def list_summaries(self, limit: int = 50) -> list[RankingRunSummaryItem]:
        from app.ranking.schemas import RankingRunSummaryItem

        with self.session() as s:
            stmt = (
                select(
                    RankingRunModel.run_id,
                    RankingRunModel.evaluated_at,
                    RankingRunModel.dataset_id,
                    RankingRunModel.extraction_run_id,
                    RankingRunModel.scoring_run_id,
                    RankingRunModel.eligibility_run_id,
                    RankingRunModel.top_x,
                    RankingRunModel.include_needs_review,
                    RankingRunModel.tiebreak_criterion_id,
                    RankingRunModel.selected_count,
                    RankingRunModel.shortage,
                    RankingRunModel.payload["summary"].label("summary_json"),
                    EligibilityRunModel.config_id.label("eligibility_config_id"),
                    EligibilityRunModel.config_version.label("eligibility_config_version"),
                    ScoringRunModel.config_id.label("scoring_config_id"),
                    ScoringRunModel.config_version.label("scoring_config_version"),
                    ScoringRunModel.config_source.label("scoring_config_source"),
                    DatasetModel.filename.label("dataset_filename"),
                )
                .outerjoin(
                    EligibilityRunModel,
                    RankingRunModel.eligibility_run_id == EligibilityRunModel.run_id,
                )
                .outerjoin(
                    ScoringRunModel,
                    RankingRunModel.scoring_run_id == ScoringRunModel.run_id,
                )
                .outerjoin(
                    DatasetModel,
                    RankingRunModel.dataset_id == DatasetModel.dataset_id,
                )
                .order_by(
                    RankingRunModel.evaluated_at.desc(), RankingRunModel.run_id.desc()
                )
                .limit(limit)
            )
            rows = s.execute(stmt).all()
            summaries = []
            for r in rows:
                summary_data = r.summary_json or {}
                selected_val = int(summary_data.get("selected_teams_count", r.selected_count or 0))
                shortage_val = int(summary_data.get("shortage", r.shortage or 0))
                needs_review_val = int(summary_data.get("needs_review_count", 0))
                excluded_val = int(summary_data.get("excluded_count", 0))
                unresolved_val = int(summary_data.get("unresolved_count", 0))
                tie_val = bool(summary_data.get("tie_at_cutoff", False))

                summaries.append(
                    RankingRunSummaryItem(
                        run_id=r.run_id,
                        evaluated_at=(
                            r.evaluated_at.isoformat()
                            if hasattr(r.evaluated_at, "isoformat")
                            else str(r.evaluated_at)
                        ),
                        dataset_id=r.dataset_id,
                        extraction_run_id=r.extraction_run_id,
                        scoring_run_id=r.scoring_run_id,
                        eligibility_run_id=r.eligibility_run_id,
                        top_x=r.top_x,
                        include_needs_review=r.include_needs_review,
                        tiebreak_criterion_id=r.tiebreak_criterion_id,
                        selected_teams_count=selected_val,
                        selected=selected_val,
                        shortage=shortage_val,
                        needs_review_count=needs_review_val,
                        needs_review=needs_review_val,
                        excluded_count=excluded_val,
                        excluded=excluded_val,
                        unresolved_count=unresolved_val,
                        unresolved=unresolved_val,
                        tie_at_cutoff=tie_val,
                        eligibility_config_id=r.eligibility_config_id,
                        eligibility_config_version=r.eligibility_config_version,
                        scoring_config_id=r.scoring_config_id,
                        scoring_config_version=r.scoring_config_version,
                        scoring_config_source=r.scoring_config_source,
                        dataset_filename=r.dataset_filename,
                    )
                )
            return summaries

    def delete(self, run_id: str) -> bool:
        """Delete ranking run by run_id. Returns True if deleted, False if not found."""
        with self.session() as s:
            stmt = select(RankingRunModel).where(RankingRunModel.run_id == run_id)
            row = s.execute(stmt).scalars().first()
            if row is None:
                return False
            s.delete(row)
            return True

    def reset(self) -> None:
        """Test isolation helper: clears all ranking runs."""
        self._assert_safe_reset()
        with self.session() as s:
            s.execute(sa.text("DELETE FROM ranking_runs;"))


# ---------------------------------------------------------------------------
# 7. Dataset Store
# ---------------------------------------------------------------------------


class PostgresDatasetStore(BasePostgresStore):
    """PostgreSQL store for uploaded and validated registration datasets."""

    def save(self, record: DatasetRecord) -> DatasetRecord:
        derived = derive_dataset_columns(
            payload=record.payload or record.model_dump(),
            dataset_id=record.dataset_id,
            filename=record.filename,
            file_type=record.file_type,
            uploaded_at=record.uploaded_at,
            mapping=record.mapping,
            teams_count=record.teams_count,
            members_count=record.members_count,
            warnings=record.warnings,
            unmapped_fields=record.unmapped_fields,
        )
        stmt = pg_insert(DatasetModel).values(**derived)
        stmt = stmt.on_conflict_do_update(
            index_elements=["dataset_id"],
            set_={
                "filename": stmt.excluded.filename,
                "file_type": stmt.excluded.file_type,
                "teams_count": stmt.excluded.teams_count,
                "members_count": stmt.excluded.members_count,
                "uploaded_at": stmt.excluded.uploaded_at,
                "mapping": stmt.excluded.mapping,
                "warnings": stmt.excluded.warnings,
                "unmapped_fields": stmt.excluded.unmapped_fields,
                "payload": stmt.excluded.payload,
            },
        )
        with self.session() as s:
            s.execute(stmt)
        return record

    def get(self, dataset_id: str) -> Optional[DatasetRecord]:
        from app.schemas.ingestion import DatasetRecord

        with self.session() as s:
            stmt = select(DatasetModel).where(DatasetModel.dataset_id == dataset_id)
            row = s.execute(stmt).scalars().first()
            if row is None:
                return None
            return DatasetRecord(
                dataset_id=row.dataset_id,
                filename=row.filename,
                file_type=row.file_type,
                teams_count=row.teams_count,
                members_count=row.members_count,
                uploaded_at=(
                    row.uploaded_at.isoformat()
                    if hasattr(row.uploaded_at, "isoformat")
                    else str(row.uploaded_at)
                ),
                mapping=row.mapping,
                warnings=row.warnings,
                unmapped_fields=row.unmapped_fields,
                created_at=(
                    row.created_at.isoformat()
                    if hasattr(row.created_at, "isoformat")
                    else str(row.created_at)
                ),
                payload=row.payload,
            )

    def list_datasets(self) -> list[DatasetRecord]:
        from app.schemas.ingestion import DatasetRecord

        with self.session() as s:
            stmt = select(DatasetModel).order_by(DatasetModel.uploaded_at.desc())
            rows = s.execute(stmt).scalars().all()
            return [
                DatasetRecord(
                    dataset_id=row.dataset_id,
                    filename=row.filename,
                    file_type=row.file_type,
                    teams_count=row.teams_count,
                    members_count=row.members_count,
                    uploaded_at=(
                        row.uploaded_at.isoformat()
                        if hasattr(row.uploaded_at, "isoformat")
                        else str(row.uploaded_at)
                    ),
                    mapping=row.mapping,
                    warnings=row.warnings,
                    unmapped_fields=row.unmapped_fields,
                    created_at=(
                        row.created_at.isoformat()
                        if hasattr(row.created_at, "isoformat")
                        else str(row.created_at)
                    ),
                    payload=row.payload,
                )
                for row in rows
            ]

    def list_summaries(self, limit: int = 50) -> list[DatasetSummary]:
        from app.schemas.ingestion import DatasetSummary

        warnings_count_expr = sa.case(
            (
                func.jsonb_typeof(DatasetModel.warnings) == "array",
                func.jsonb_array_length(DatasetModel.warnings),
            ),
            else_=0,
        ).label("warnings_count")

        with self.session() as s:
            stmt = (
                select(
                    DatasetModel.dataset_id,
                    DatasetModel.filename,
                    DatasetModel.file_type,
                    DatasetModel.teams_count,
                    DatasetModel.members_count,
                    DatasetModel.uploaded_at,
                    warnings_count_expr,
                )
                .order_by(DatasetModel.uploaded_at.desc(), DatasetModel.dataset_id.desc())
                .limit(limit)
            )
            rows = s.execute(stmt).all()
            return [
                DatasetSummary(
                    dataset_id=r.dataset_id,
                    filename=r.filename,
                    file_type=r.file_type,
                    teams_count=r.teams_count,
                    members_count=r.members_count,
                    uploaded_at=(
                        r.uploaded_at.isoformat()
                        if hasattr(r.uploaded_at, "isoformat")
                        else str(r.uploaded_at)
                    ),
                    warnings_count=r.warnings_count,
                )
                for r in rows
            ]

    def get_dependent_counts(self, dataset_id: str) -> dict[str, int]:
        """Count downstream runs that reference this dataset directly or via its extractions."""
        with self.session() as s:
            # Find extraction run IDs for this dataset
            ext_ids_q = select(ExtractionRunModel.run_id).where(ExtractionRunModel.dataset_id == dataset_id)
            ext_ids = list(s.execute(ext_ids_q).scalars().all())

            ranking_cond = [RankingRunModel.dataset_id == dataset_id]
            scoring_cond = [ScoringRunModel.dataset_id == dataset_id]
            elig_cond = [EligibilityRunModel.dataset_id == dataset_id]
            if ext_ids:
                ranking_cond.append(RankingRunModel.extraction_run_id.in_(ext_ids))
                scoring_cond.append(ScoringRunModel.extraction_run_id.in_(ext_ids))
                elig_cond.append(EligibilityRunModel.extraction_run_id.in_(ext_ids))

            ranking_count = s.execute(select(func.count()).select_from(RankingRunModel).where(sa.or_(*ranking_cond))).scalar() or 0
            scoring_count = s.execute(select(func.count()).select_from(ScoringRunModel).where(sa.or_(*scoring_cond))).scalar() or 0
            elig_count = s.execute(select(func.count()).select_from(EligibilityRunModel).where(sa.or_(*elig_cond))).scalar() or 0
            ext_count = len(ext_ids)

            return {
                "ranking_runs": int(ranking_count),
                "scoring_runs": int(scoring_count),
                "eligibility_runs": int(elig_count),
                "extraction_runs": int(ext_count),
                "total": int(ranking_count + scoring_count + elig_count + ext_count),
            }

    def delete(self, dataset_id: str, cascade: bool = False) -> bool:
        """Delete dataset with safe transactional cascade."""
        with self.session() as s:
            stmt = select(DatasetModel).where(DatasetModel.dataset_id == dataset_id)
            row = s.execute(stmt).scalars().first()
            if row is None:
                return False

            if not cascade:
                s.delete(row)
                return True

            ext_ids_q = select(ExtractionRunModel.run_id).where(ExtractionRunModel.dataset_id == dataset_id)
            ext_ids = list(s.execute(ext_ids_q).scalars().all())

            ranking_cond = [RankingRunModel.dataset_id == dataset_id]
            scoring_cond = [ScoringRunModel.dataset_id == dataset_id]
            elig_cond = [EligibilityRunModel.dataset_id == dataset_id]
            if ext_ids:
                ranking_cond.append(RankingRunModel.extraction_run_id.in_(ext_ids))
                scoring_cond.append(ScoringRunModel.extraction_run_id.in_(ext_ids))
                elig_cond.append(EligibilityRunModel.extraction_run_id.in_(ext_ids))

            # Cascade deletion in child-first order to satisfy ON DELETE RESTRICT
            s.execute(sa.delete(RankingRunModel).where(sa.or_(*ranking_cond)))
            s.execute(sa.delete(ScoringRunModel).where(sa.or_(*scoring_cond)))
            elig_ids = list(s.execute(select(EligibilityRunModel.run_id).where(sa.or_(*elig_cond))).scalars().all())
            if elig_ids:
                s.execute(sa.delete(ManualOverrideModel).where(ManualOverrideModel.run_id.in_(elig_ids)))
                s.execute(sa.delete(EligibilityRunModel).where(EligibilityRunModel.run_id.in_(elig_ids)))
            if ext_ids:
                s.execute(sa.delete(ExtractionRunModel).where(ExtractionRunModel.run_id.in_(ext_ids)))

            s.delete(row)
            return True

    def reset(self) -> None:
        """Test isolation helper: clears all dataset records."""
        self._assert_safe_reset()
        with self.session() as s:
            s.execute(sa.text("DELETE FROM datasets;"))


# ---------------------------------------------------------------------------
# 8. Extraction Run Store
# ---------------------------------------------------------------------------


class PostgresExtractionRunStore(BasePostgresStore):
    """PostgreSQL store for historical signal extraction runs."""

    def save(self, record: ExtractionRunResponse) -> None:
        derived = derive_extraction_run_columns(record)
        stmt = pg_insert(ExtractionRunModel).values(**derived)
        stmt = stmt.on_conflict_do_update(
            index_elements=["run_id"],
            set_={
                "dataset_id": stmt.excluded.dataset_id,
                "selected_signals": stmt.excluded.selected_signals,
                "analyzers_executed": stmt.excluded.analyzers_executed,
                "total_teams": stmt.excluded.total_teams,
                "total_members": stmt.excluded.total_members,
                "payload": stmt.excluded.payload,
            },
        )
        with self.session() as s:
            s.execute(stmt)

    def get(self, run_id: str) -> Optional[ExtractionRunResponse]:
        from app.signals.schemas import ExtractionRunResponse

        with self.session() as s:
            stmt = select(ExtractionRunModel).where(ExtractionRunModel.run_id == run_id)
            row = s.execute(stmt).scalars().first()
            if row is None:
                return None
            return ExtractionRunResponse.model_validate(row.payload)

    def list_runs(self, dataset_id: Optional[str] = None) -> list[ExtractionRunResponse]:
        from app.signals.schemas import ExtractionRunResponse

        with self.session() as s:
            stmt = select(ExtractionRunModel)
            if dataset_id:
                stmt = stmt.where(ExtractionRunModel.dataset_id == dataset_id)
            stmt = stmt.order_by(ExtractionRunModel.created_at.desc())
            rows = s.execute(stmt).scalars().all()
            return [ExtractionRunResponse.model_validate(r.payload) for r in rows]

    def list_summaries(
        self, limit: int = 50, dataset_id: Optional[str] = None
    ) -> list[ExtractionRunSummary]:
        from app.signals.schemas import ExtractionRunSummary

        warnings_count_expr = sa.case(
            (
                func.jsonb_typeof(ExtractionRunModel.payload["warnings"]) == "array",
                func.jsonb_array_length(ExtractionRunModel.payload["warnings"]),
            ),
            else_=0,
        ).label("warnings_count")

        errors_count_expr = sa.case(
            (
                func.jsonb_typeof(ExtractionRunModel.payload["errors"]) == "array",
                func.jsonb_array_length(ExtractionRunModel.payload["errors"]),
            ),
            else_=0,
        ).label("errors_count")

        with self.session() as s:
            stmt = select(
                ExtractionRunModel.run_id,
                ExtractionRunModel.dataset_id,
                ExtractionRunModel.created_at,
                ExtractionRunModel.selected_signals,
                ExtractionRunModel.total_teams,
                ExtractionRunModel.total_members,
                warnings_count_expr,
                errors_count_expr,
            )
            if dataset_id:
                stmt = stmt.where(ExtractionRunModel.dataset_id == dataset_id)
            stmt = stmt.order_by(
                ExtractionRunModel.created_at.desc(), ExtractionRunModel.run_id.desc()
            ).limit(limit)
            rows = s.execute(stmt).all()
            return [
                ExtractionRunSummary(
                    run_id=r.run_id,
                    dataset_id=r.dataset_id,
                    created_at=(
                        r.created_at.isoformat()
                        if hasattr(r.created_at, "isoformat")
                        else str(r.created_at)
                    ),
                    selected_signals=list(r.selected_signals or []),
                    total_teams=r.total_teams,
                    total_members=r.total_members,
                    warnings_count=r.warnings_count,
                    errors_count=r.errors_count,
                )
                for r in rows
            ]

    def get_dependent_counts(self, run_id: str) -> dict[str, int]:
        """Count downstream runs that reference this extraction run."""
        with self.session() as s:
            ranking_count = s.execute(
                select(func.count()).select_from(RankingRunModel).where(RankingRunModel.extraction_run_id == run_id)
            ).scalar() or 0
            scoring_count = s.execute(
                select(func.count()).select_from(ScoringRunModel).where(ScoringRunModel.extraction_run_id == run_id)
            ).scalar() or 0
            elig_count = s.execute(
                select(func.count()).select_from(EligibilityRunModel).where(EligibilityRunModel.extraction_run_id == run_id)
            ).scalar() or 0

            return {
                "ranking_runs": int(ranking_count),
                "scoring_runs": int(scoring_count),
                "eligibility_runs": int(elig_count),
                "total": int(ranking_count + scoring_count + elig_count),
            }

    def delete(self, run_id: str, cascade: bool = False) -> bool:
        """Delete extraction run with safe transactional cascade."""
        with self.session() as s:
            stmt = select(ExtractionRunModel).where(ExtractionRunModel.run_id == run_id)
            row = s.execute(stmt).scalars().first()
            if row is None:
                return False

            if not cascade:
                s.delete(row)
                return True

            # Cascade in child-first order
            s.execute(sa.delete(RankingRunModel).where(RankingRunModel.extraction_run_id == run_id))
            s.execute(sa.delete(ScoringRunModel).where(ScoringRunModel.extraction_run_id == run_id))
            elig_ids = list(s.execute(select(EligibilityRunModel.run_id).where(EligibilityRunModel.extraction_run_id == run_id)).scalars().all())
            if elig_ids:
                s.execute(sa.delete(ManualOverrideModel).where(ManualOverrideModel.run_id.in_(elig_ids)))
                s.execute(sa.delete(EligibilityRunModel).where(EligibilityRunModel.run_id.in_(elig_ids)))

            s.delete(row)
            return True

    def reset(self) -> None:

        """Test isolation helper: clears all extraction runs."""
        self._assert_safe_reset()
        with self.session() as s:
            s.execute(sa.text("DELETE FROM extraction_runs;"))

