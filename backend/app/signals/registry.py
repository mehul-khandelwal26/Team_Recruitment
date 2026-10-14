"""Default registry and standard extractor specifications.

Maintains registered extractors, categories, and contracts for active and planned
signal extractors.
"""

from __future__ import annotations

from app.schemas.ingestion import MemberSchema
from app.signals.academic import AcademicMetricsAnalyzer
from app.signals.base import BaseSignalExtractor, SignalExtractorRegistry
from app.signals.github import GitHubAnalyzer
from app.signals.resume import ResumeSignalExtractor
from app.signals.schemas import (
    CategoryDefinition,
    ExtractedSignal,
    ExtractorDescriptor,
    SignalDefinition,
    SignalStatus,
)


# ---------------------------------------------------------------------------
# Planned Future Extractor Specifications (Contracts / Placeholders)
# ---------------------------------------------------------------------------




class PortfolioAnalyzerContract(BaseSignalExtractor):
    """Contract specification for candidate portfolio website inspection."""

    @property
    def descriptor(self) -> ExtractorDescriptor:
        return ExtractorDescriptor(
            extractor_id="portfolio_analyzer",
            name="Portfolio Website Inspector",
            description="Checks portfolio website reachability, project showcase presence, and live demos.",
            category="portfolio",
            required_inputs=["portfolio_url"],
            optional_inputs=[],
            produced_signals=[
                "portfolio_site_reachable",
                "portfolio_has_live_projects",
            ],
            signals=[
                SignalDefinition(
                    signal_key="portfolio_site_reachable",
                    name="Portfolio Site Reachable",
                    description="Verifies that the candidate portfolio link is live.",
                    category="portfolio",
                    value_type="boolean",
                ),
                SignalDefinition(
                    signal_key="portfolio_has_live_projects",
                    name="Live Projects Detected",
                    description="Identifies demonstrable projects on portfolio.",
                    category="portfolio",
                    value_type="boolean",
                ),
            ],
            is_enabled_by_default=False,
        )

    def extract(
        self,
        member: MemberSchema,
        selected_signals: set[str] | None = None,
        config: dict | None = None,
    ) -> list[ExtractedSignal]:
        return [
            ExtractedSignal(
                signal_key="portfolio_site_reachable",
                category="portfolio",
                status=SignalStatus.PENDING,
            )
        ]


# Backward compatibility aliases for existing contract imports
GitHubAnalyzerContract = GitHubAnalyzer
AcademicMetricsContract = AcademicMetricsAnalyzer


# ---------------------------------------------------------------------------
# Global Registry Initialization
# ---------------------------------------------------------------------------


def create_default_registry() -> SignalExtractorRegistry:
    """Instantiate and register standard analyzers and categories."""
    registry = SignalExtractorRegistry()

    # Register standard categories
    registry.register_category(
        CategoryDefinition(
            category_id="technical",
            name="Technical & GitHub",
            description="Public code repositories, activity recency, and technical profile verification.",
            signal_keys=[
                "github_public_repo_count",
                "github_repo_metadata",
                "github_recent_activity",
                "github_profile_verified",
            ],
        )
    )
    registry.register_category(
        CategoryDefinition(
            category_id="academic",
            name="Academics",
            description="Normalized CGPA, CPI, and academic year records from registration data.",
            signal_keys=[
                "academic_cgpa",
                "academic_year",
                "normalized_cgpa_10_scale",
            ],
        )
    )
    registry.register_category(
        CategoryDefinition(
            category_id="experience",
            name="Experience & Resume",
            description="Extracted candidate resume skills, projects, education, experience, achievements, and links.",
            signal_keys=[
                "resume_extracted_skills",
                "resume_programming_languages",
                "resume_frameworks_libraries",
                "resume_databases",
                "resume_tools_technologies",
                "resume_projects",
                "resume_education",
                "resume_degree_level",
                "resume_experience",
                "resume_experience_years",
                "resume_certifications_achievements",
                "resume_external_links",
            ],
        )
    )
    registry.register_category(
        CategoryDefinition(
            category_id="portfolio",
            name="Portfolio",
            description="Candidate portfolio website inspection and live demo presence (planned).",
            signal_keys=[
                "portfolio_site_reachable",
                "portfolio_has_live_projects",
            ],
        )
    )

    # Register active functional analyzers
    registry.register(GitHubAnalyzer())
    registry.register(AcademicMetricsAnalyzer())
    registry.register(ResumeSignalExtractor())

    # Register future planned contracts
    registry.register(PortfolioAnalyzerContract())

    return registry


default_signal_registry = create_default_registry()
