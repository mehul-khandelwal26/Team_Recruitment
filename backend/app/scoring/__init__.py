"""Weighted scoring and team aggregation engine package."""

from app.scoring.config_store import ScoringConfigStore, default_scoring_config_store
from app.scoring.engine import calculate_team_score, evaluate_scoring
from app.scoring.presets import get_default_scoring_presets
from app.scoring.schemas import (
    AggregationMethod,
    CriterionScoreBreakdown,
    CriterionType,
    EvaluationCriterion,
    LinearRangeConfig,
    MissingDataPolicy,
    NormalizationConfig,
    ScoreStatus,
    ScoringConfiguration,
    ScoringRunResponse,
    TeamScoringResult,
)
from app.scoring.store import InMemoryScoringRunStore, default_scoring_run_store
from app.scoring.validation import validate_scoring_configuration, validate_scoring_criterion

__all__ = [
    "AggregationMethod",
    "CriterionScoreBreakdown",
    "CriterionType",
    "EvaluationCriterion",
    "InMemoryScoringRunStore",
    "LinearRangeConfig",
    "MissingDataPolicy",
    "NormalizationConfig",
    "ScoreStatus",
    "ScoringConfigStore",
    "ScoringConfiguration",
    "ScoringRunResponse",
    "TeamScoringResult",
    "calculate_team_score",
    "default_scoring_config_store",
    "default_scoring_run_store",
    "evaluate_scoring",
    "get_default_scoring_presets",
    "validate_scoring_configuration",
    "validate_scoring_criterion",
]
