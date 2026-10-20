"""Tests for fuzzy column confidence matching and generalized proportional scoring.

Verifies:
1. Field name confidence matching (e.g. 'skills' <-> 'candidate_skills', 'city' <-> 'current_city').
2. Proportional keyword matching (k / N) and full score (1.0).
3. Any-match strategy for single-selection preferences.
4. Correctness of audit explainability strings.
"""

from __future__ import annotations

import pytest
from app.schemas.ingestion import MemberSchema, TeamSchema
from app.scoring.engine import compute_field_confidence, normalize_value, resolve_member_signal_or_field
from app.scoring.schemas import (
    AggregationMethod,
    CategoricalMappingConfig,
    CriterionType,
    EvaluationCriterion,
    NormalizationConfig,
)


def test_field_confidence_computation():
    """Verify compute_field_confidence accurately scores similarities."""
    # Exact match
    assert compute_field_confidence("skills", "skills") == 1.0
    assert compute_field_confidence("custom:skills", "skills") == 1.0
    assert compute_field_confidence("skills", "custom:skills") == 1.0

    # Plural / singular
    assert compute_field_confidence("skills", "skill") >= 0.95
    assert compute_field_confidence("skill", "skills") >= 0.95

    # Token overlap with prefixes / suffixes
    assert compute_field_confidence("skills", "candidate_skills") >= 0.85
    assert compute_field_confidence("skills", "technical_skills") >= 0.85
    assert compute_field_confidence("skills", "skills_list") >= 0.85
    assert compute_field_confidence("city", "current_city") >= 0.85
    assert compute_field_confidence("track", "hackathon_track") >= 0.85

    # Completely unrelated fields should be 0.0 or well below 0.80
    assert compute_field_confidence("skills", "phone_number") == 0.0
    assert compute_field_confidence("skills", "email") == 0.0
    assert compute_field_confidence("skills", "college_name") == 0.0


def test_column_discovery_in_member_data():
    """Verify resolve_member_signal_or_field binds to column using confidence matching."""
    member = MemberSchema(
        member_id="m_101",
        name="Alice Walker",
        email="alice@example.com",
        custom_fields={
            "candidate_skills": "Python, C++, Docker, Git",
            "current_city": "Bangalore",
        },
        raw_data={},
    )

    # Looking for target "skills" (which maps to candidate_skills)
    val, status, provenance, conf = resolve_member_signal_or_field(
        member=member,
        signal_key="custom:skills",
        signals_by_member={},
    )
    assert status == "extracted"
    assert val == "Python, C++, Docker, Git"
    assert conf is not None and conf >= 0.85
    assert "candidate_skills" in provenance

    # Looking for target "city" (which maps to current_city)
    val_city, status_city, provenance_city, conf_city = resolve_member_signal_or_field(
        member=member,
        signal_key="custom:city",
        signals_by_member={},
    )
    assert status_city == "extracted"
    assert val_city == "Bangalore"
    assert conf_city is not None and conf_city >= 0.85
    assert "current_city" in provenance_city


def test_proportional_keyword_scoring():
    """Verify normalize_value accurately calculates proportional keyword match scores."""
    criterion = EvaluationCriterion(
        criterion_id="crit_skills_match",
        name="Technical Skills",
        target_signal_key="custom:skills",
        criterion_type=CriterionType.CATEGORICAL,
        weight=1.0,
        is_enabled=True,
        normalization=NormalizationConfig(
            categorical_mapping=CategoricalMappingConfig(
                category_scores={"Python": 1.0, "JavaScript": 1.0, "C++": 1.0},
                default_score=0.0,
                case_sensitive=False,
            )
        ),
        aggregation=AggregationMethod.MEAN,
        config={
            "is_custom_field": True,
            "expected_values": ["Python", "JavaScript", "C++"],
            "match_mode": "proportional",
        },
    )

    # 1. Full Match: 3 of 3 (Python, JavaScript, C++)
    score_full, expl_full = normalize_value("Proficient in Python, JavaScript, and C++.", criterion)
    assert score_full == 1.0
    assert "Matched 3 of 3 expected item(s)" in expl_full

    # 2. Partial Match: 2 of 3 (Python, C++)
    score_2_3, expl_2_3 = normalize_value("Python, C++, Docker, Linux", criterion)
    assert pytest.approx(score_2_3, 0.001) == 2 / 3
    assert "Matched 2 of 3 expected item(s) (Python, C++)" in expl_2_3

    # 3. Partial Match: 1 of 3 (JavaScript only)
    score_1_3, expl_1_3 = normalize_value("Frontend dev with JavaScript and React", criterion)
    assert pytest.approx(score_1_3, 0.001) == 1 / 3
    assert "Matched 1 of 3 expected item(s) (JavaScript)" in expl_1_3

    # 4. Zero Match: 0 of 3
    score_zero, expl_zero = normalize_value("Rust, Golang, Elixir", criterion)
    assert score_zero == 0.0
    assert "Matched 0 of 3 expected item(s) (none)" in expl_zero


def test_any_match_strategy():
    """Verify any match mode assigns 1.0 if at least one expected value is found."""
    criterion_location = EvaluationCriterion(
        criterion_id="crit_location",
        name="Preferred Location",
        target_signal_key="custom:city",
        criterion_type=CriterionType.CATEGORICAL,
        weight=1.0,
        is_enabled=True,
        normalization=NormalizationConfig(
            categorical_mapping=CategoricalMappingConfig(
                category_scores={"Bangalore": 1.0, "Mumbai": 1.0},
                default_score=0.0,
                case_sensitive=False,
            )
        ),
        aggregation=AggregationMethod.MEAN,
        config={
            "is_custom_field": True,
            "expected_values": ["Bangalore", "Mumbai"],
            "match_mode": "any",
        },
    )

    # Matches Bangalore -> 1.0
    score_blr, expl_blr = normalize_value("Bangalore, Karnataka", criterion_location)
    assert score_blr == 1.0
    assert "Matched 1 expected item(s) (Bangalore)" in expl_blr

    # Matches neither -> 0.0
    score_delhi, expl_delhi = normalize_value("New Delhi", criterion_location)
    assert score_delhi == 0.0
    assert "Matched 0 expected item(s) (none)" in expl_delhi
