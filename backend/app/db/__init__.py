"""Database connection, models, and session management."""

from app.db.base import Base
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
from app.db.session import (
    assert_safe_test_database,
    create_app_engine,
    get_session_factory,
    is_database_unavailable_error,
    session_scope,
)

__all__ = [
    "Base",
    "RuleConfigurationModel",
    "EligibilityRunModel",
    "ManualOverrideModel",
    "ScoringConfigurationModel",
    "ScoringRunModel",
    "RankingRunModel",
    "DatasetModel",
    "ExtractionRunModel",
    "derive_rule_configuration_columns",
    "derive_eligibility_run_columns",
    "derive_manual_override_columns",
    "derive_scoring_configuration_columns",
    "derive_scoring_run_columns",
    "derive_ranking_run_columns",
    "derive_dataset_columns",
    "derive_extraction_run_columns",
    "create_app_engine",
    "get_session_factory",
    "session_scope",
    "assert_safe_test_database",
    "is_database_unavailable_error",
]
