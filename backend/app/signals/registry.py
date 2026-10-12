"""Default registry and standard extractor specifications.

Provides ready-to-inspect descriptors for planned future extractors
without running external network or heavy ML operations.
"""

from __future__ import annotations

from app.signals.base import BaseSignalExtractor, SignalExtractorRegistry
from app.signals.schemas import ExtractedSignal, ExtractorDescriptor, SignalStatus
from app.schemas.ingestion import MemberSchema


# ---------------------------------------------------------------------------
# Standard Extractor Specifications (Contracts)
# ---------------------------------------------------------------------------


class GitHubAnalyzerContract(BaseSignalExtractor):
    """Specification for future GitHub repository and commit analysis."""

    @property
    def descriptor(self) -> ExtractorDescriptor:
        return ExtractorDescriptor(
            extractor_id="github_analyzer",
            name="GitHub Activity & Repo Analyzer",
            description="Analyzes public repositories, commit recency, primary languages, and contributions.",
            category="technical",
            required_inputs=["github_url"],
            optional_inputs=["name"],
            produced_signals=[
                "github_public_repo_count",
                "github_recent_commit_activity",
                "github_primary_languages",
                "github_profile_verified",
            ],
            is_enabled_by_default=False,
        )

    def extract(self, member: MemberSchema) -> list[ExtractedSignal]:
        # Staged for future implementation - returns pending contract
        return [
            ExtractedSignal(
                signal_key="github_profile_verified",
                category="technical",
                status=SignalStatus.PENDING,
            )
        ]


class ResumeParserContract(BaseSignalExtractor):
    """Specification for future PDF/Word resume analysis."""

    @property
    def descriptor(self) -> ExtractorDescriptor:
        return ExtractorDescriptor(
            extractor_id="resume_parser",
            name="Resume & CV Skill Extractor",
            description="Parses uploaded resumes for technical skills, years of experience, and education.",
            category="experience",
            required_inputs=["resume_url"],
            optional_inputs=[],
            produced_signals=[
                "resume_extracted_skills",
                "resume_experience_years",
                "resume_degree_level",
            ],
            is_enabled_by_default=False,
        )

    def extract(self, member: MemberSchema) -> list[ExtractedSignal]:
        return [
            ExtractedSignal(
                signal_key="resume_extracted_skills",
                category="experience",
                status=SignalStatus.PENDING,
            )
        ]


class AcademicMetricsContract(BaseSignalExtractor):
    """Specification for academic score processing."""

    @property
    def descriptor(self) -> ExtractorDescriptor:
        return ExtractorDescriptor(
            extractor_id="academic_metrics",
            name="Academic Metrics Processor",
            description="Normalizes CGPA, CPI, and academic standings across diverse grading scales.",
            category="academic",
            required_inputs=["cgpa"],
            optional_inputs=["academic_year"],
            produced_signals=[
                "normalized_cgpa_10_scale",
                "academic_standing_category",
            ],
            is_enabled_by_default=False,
        )

    def extract(self, member: MemberSchema) -> list[ExtractedSignal]:
        return [
            ExtractedSignal(
                signal_key="normalized_cgpa_10_scale",
                category="academic",
                status=SignalStatus.PENDING,
            )
        ]


class PortfolioAnalyzerContract(BaseSignalExtractor):
    """Specification for candidate portfolio website inspection."""

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
            is_enabled_by_default=False,
        )

    def extract(self, member: MemberSchema) -> list[ExtractedSignal]:
        return [
            ExtractedSignal(
                signal_key="portfolio_site_reachable",
                category="portfolio",
                status=SignalStatus.PENDING,
            )
        ]


# ---------------------------------------------------------------------------
# Global Registry Instance
# ---------------------------------------------------------------------------


default_signal_registry = SignalExtractorRegistry()
default_signal_registry.register(GitHubAnalyzerContract())
default_signal_registry.register(ResumeParserContract())
default_signal_registry.register(AcademicMetricsContract())
default_signal_registry.register(PortfolioAnalyzerContract())
