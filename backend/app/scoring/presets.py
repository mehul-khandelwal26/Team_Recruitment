"""Standard scoring presets for hackathons and recruitment evaluations."""

from __future__ import annotations

from app.scoring.schemas import (
    AggregationMethod,
    BooleanMappingConfig,
    CategoricalMappingConfig,
    CriterionType,
    EvaluationCriterion,
    LinearRangeConfig,
    MissingDataPolicy,
    NormalizationConfig,
    ScoringConfiguration,
)


def get_default_scoring_presets() -> list[ScoringConfiguration]:
    """Return standard out-of-the-box scoring configuration presets."""
    return [
        # 1. Balanced Preset
        ScoringConfiguration(
            config_id="balanced",
            name="Balanced Evaluation",
            version=1,
            user_id="system",
            description="Balanced weighting across GitHub activity, academic records, and technical experience.",
            scale_max=100.0,
            criteria=[
                EvaluationCriterion(
                    criterion_id="github_repos",
                    name="GitHub Public Repositories",
                    description="Public repository count normalized linearly from 0 to 20.",
                    target_signal_key="github_public_repo_count",
                    criterion_type=CriterionType.NUMERIC_RANGE,
                    weight=35.0,
                    normalization=NormalizationConfig(
                        linear_range=LinearRangeConfig(min_value=0.0, max_value=20.0),
                    ),
                    aggregation=AggregationMethod.MEAN,
                    missing_data_policy=MissingDataPolicy.EXCLUDE_AND_RENORMALIZE,
                ),
                EvaluationCriterion(
                    criterion_id="academic_cgpa",
                    name="Academic CGPA Score",
                    description="Academic performance normalized between 6.0 and 10.0.",
                    target_signal_key="academic_cgpa",
                    criterion_type=CriterionType.NUMERIC_RANGE,
                    weight=35.0,
                    normalization=NormalizationConfig(
                        linear_range=LinearRangeConfig(min_value=6.0, max_value=10.0),
                    ),
                    aggregation=AggregationMethod.MEAN,
                    missing_data_policy=MissingDataPolicy.EXCLUDE_AND_RENORMALIZE,
                ),
                EvaluationCriterion(
                    criterion_id="experience_years",
                    name="Technical Experience",
                    description="Years of resume-derived technical experience normalized up to 4 years.",
                    target_signal_key="resume_experience_years",
                    criterion_type=CriterionType.NUMERIC_RANGE,
                    weight=20.0,
                    normalization=NormalizationConfig(
                        linear_range=LinearRangeConfig(min_value=0.0, max_value=4.0),
                    ),
                    aggregation=AggregationMethod.MEAN,
                    missing_data_policy=MissingDataPolicy.EXCLUDE_AND_RENORMALIZE,
                ),
                EvaluationCriterion(
                    criterion_id="profile_verified",
                    name="GitHub Profile Verified",
                    description="Confirmation that GitHub profile is publicly reachable and verified.",
                    target_signal_key="github_profile_verified",
                    criterion_type=CriterionType.BOOLEAN,
                    weight=10.0,
                    normalization=NormalizationConfig(
                        boolean_mapping=BooleanMappingConfig(true_score=1.0, false_score=0.0),
                    ),
                    aggregation=AggregationMethod.MAX,
                    missing_data_policy=MissingDataPolicy.EXCLUDE_AND_RENORMALIZE,
                ),
            ],
        ),

        # 2. Technical Heavy Preset
        ScoringConfiguration(
            config_id="technical_heavy",
            name="Technical & Open Source Heavy",
            version=1,
            user_id="system",
            description="Prioritizes verified open-source contributions and development experience.",
            scale_max=100.0,
            criteria=[
                EvaluationCriterion(
                    criterion_id="github_repos",
                    name="GitHub Public Repositories",
                    description="Repository count scaled up to 30 repos, aggregated using best-in-team max.",
                    target_signal_key="github_public_repo_count",
                    criterion_type=CriterionType.NUMERIC_RANGE,
                    weight=45.0,
                    normalization=NormalizationConfig(
                        linear_range=LinearRangeConfig(min_value=0.0, max_value=30.0),
                    ),
                    aggregation=AggregationMethod.MAX,
                    missing_data_policy=MissingDataPolicy.EXCLUDE_AND_RENORMALIZE,
                ),
                EvaluationCriterion(
                    criterion_id="experience_years",
                    name="Technical Experience",
                    description="Years of experience scaled up to 5 years, aggregated using best-in-team max.",
                    target_signal_key="resume_experience_years",
                    criterion_type=CriterionType.NUMERIC_RANGE,
                    weight=35.0,
                    normalization=NormalizationConfig(
                        linear_range=LinearRangeConfig(min_value=0.0, max_value=5.0),
                    ),
                    aggregation=AggregationMethod.MAX,
                    missing_data_policy=MissingDataPolicy.EXCLUDE_AND_RENORMALIZE,
                ),
                EvaluationCriterion(
                    criterion_id="academic_cgpa",
                    name="Academic CGPA Score",
                    description="Academic baseline score.",
                    target_signal_key="academic_cgpa",
                    criterion_type=CriterionType.NUMERIC_RANGE,
                    weight=20.0,
                    normalization=NormalizationConfig(
                        linear_range=LinearRangeConfig(min_value=6.0, max_value=10.0),
                    ),
                    aggregation=AggregationMethod.MEAN,
                    missing_data_policy=MissingDataPolicy.EXCLUDE_AND_RENORMALIZE,
                ),
            ],
        ),

        # 3. Academic Heavy Preset
        ScoringConfiguration(
            config_id="academic_heavy",
            name="Academic & Seniority Focused",
            version=1,
            user_id="system",
            description="Focuses on academic excellence and candidate batch/year progression.",
            scale_max=100.0,
            criteria=[
                EvaluationCriterion(
                    criterion_id="academic_cgpa",
                    name="Academic CGPA Score",
                    description="CGPA score normalized between 6.0 and 10.0.",
                    target_signal_key="academic_cgpa",
                    criterion_type=CriterionType.NUMERIC_RANGE,
                    weight=50.0,
                    normalization=NormalizationConfig(
                        linear_range=LinearRangeConfig(min_value=6.0, max_value=10.0),
                    ),
                    aggregation=AggregationMethod.MEAN,
                    missing_data_policy=MissingDataPolicy.EXCLUDE_AND_RENORMALIZE,
                ),
                EvaluationCriterion(
                    criterion_id="academic_year",
                    name="Seniority / Academic Year",
                    description="Scored by academic progress towards graduation.",
                    target_signal_key="academic_year",
                    criterion_type=CriterionType.CATEGORICAL,
                    weight=25.0,
                    normalization=NormalizationConfig(
                        categorical_mapping=CategoricalMappingConfig(
                            category_scores={
                                "1st Year": 0.25,
                                "2nd Year": 0.50,
                                "3rd Year": 0.75,
                                "4th Year": 1.00,
                                "Postgraduate": 1.00,
                            },
                            default_score=0.50,
                            case_sensitive=False,
                        )
                    ),
                    aggregation=AggregationMethod.MEAN,
                    missing_data_policy=MissingDataPolicy.EXCLUDE_AND_RENORMALIZE,
                ),
                EvaluationCriterion(
                    criterion_id="github_repos",
                    name="GitHub Public Repositories",
                    description="Public repository count normalized up to 15.",
                    target_signal_key="github_public_repo_count",
                    criterion_type=CriterionType.NUMERIC_RANGE,
                    weight=25.0,
                    normalization=NormalizationConfig(
                        linear_range=LinearRangeConfig(min_value=0.0, max_value=15.0),
                    ),
                    aggregation=AggregationMethod.MEAN,
                    missing_data_policy=MissingDataPolicy.EXCLUDE_AND_RENORMALIZE,
                ),
            ],
        ),

        # 4. Academic & Resume Hybrid Scorer Preset
        ScoringConfiguration(
            config_id="edge_scoring_model",
            name="Academic & Resume Hybrid Scorer",
            version=1,
            user_id="system",
            description="50% Academic CGPA + 50% Resume Experience with dynamic missing data renormalization.",
            scale_max=100.0,
            score_ineligible_teams=True,
            criteria=[
                EvaluationCriterion(
                    criterion_id="academic_cgpa",
                    name="Academic CGPA Score",
                    description="Academic performance normalized between 6.0 and 10.0.",
                    target_signal_key="academic_cgpa",
                    criterion_type=CriterionType.NUMERIC_RANGE,
                    weight=50.0,
                    normalization=NormalizationConfig(
                        linear_range=LinearRangeConfig(min_value=6.0, max_value=10.0),
                    ),
                    aggregation=AggregationMethod.MEAN,
                    missing_data_policy=MissingDataPolicy.EXCLUDE_AND_RENORMALIZE,
                ),
                EvaluationCriterion(
                    criterion_id="experience_years",
                    name="Technical Experience",
                    description="Years of resume-derived technical experience normalized up to 4 years.",
                    target_signal_key="resume_experience_years",
                    criterion_type=CriterionType.NUMERIC_RANGE,
                    weight=50.0,
                    normalization=NormalizationConfig(
                        linear_range=LinearRangeConfig(min_value=0.0, max_value=4.0),
                    ),
                    aggregation=AggregationMethod.MEAN,
                    missing_data_policy=MissingDataPolicy.EXCLUDE_AND_RENORMALIZE,
                ),
            ],
        ),
    ]
