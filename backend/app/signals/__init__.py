"""Signal extraction and analysis for candidate and team evaluations."""

from app.signals.academic import AcademicMetricsAnalyzer
from app.signals.base import BaseSignalExtractor, SignalExtractorRegistry
from app.signals.flatten import flatten_extraction_signals
from app.signals.github import GitHubAnalyzer
from app.signals.registry import default_signal_registry
from app.signals.schemas import (
    CategoryDefinition,
    ExtractedSignal,
    ExtractionRunRequest,
    ExtractionRunResponse,
    ExtractorDescriptor,
    MemberExtractionResult,
    SignalCatalogResponse,
    SignalDefinition,
    SignalEvidence,
    SignalStatus,
    TeamExtractionResult,
)
from app.signals.store import (
    ExtractionRunStoreProtocol,
    InMemoryExtractionRunStore,
    default_extraction_run_store,
)

__all__ = [
    "AcademicMetricsAnalyzer",
    "BaseSignalExtractor",
    "CategoryDefinition",
    "ExtractedSignal",
    "ExtractionRunRequest",
    "ExtractionRunResponse",
    "ExtractorDescriptor",
    "ExtractionRunStoreProtocol",
    "GitHubAnalyzer",
    "InMemoryExtractionRunStore",
    "MemberExtractionResult",
    "SignalCatalogResponse",
    "SignalDefinition",
    "SignalEvidence",
    "SignalExtractorRegistry",
    "SignalStatus",
    "TeamExtractionResult",
    "default_extraction_run_store",
    "default_signal_registry",
    "flatten_extraction_signals",
]
