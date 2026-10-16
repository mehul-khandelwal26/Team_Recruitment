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
    EligibilityRunModel,
    ManualOverrideModel,
    RankingRunModel,
    RuleConfigurationModel,
    ScoringConfigurationModel,
    ScoringRunModel,
    derive_eligibility_run_columns,
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
    from app.scoring.schemas import (
        ScoringConfiguration,
        ScoringConfigurationUpdate,
        ScoringRunResponse,
    )


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

    def reset(self) -> None:
        """Test isolation helper: clears all eligibility runs."""
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

    def reset(self) -> None:
        """Test isolation helper: clears all scoring runs."""
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

    def reset(self) -> None:
        """Test isolation helper: clears all ranking runs."""
        with self.session() as s:
            s.execute(sa.text("DELETE FROM ranking_runs;"))
