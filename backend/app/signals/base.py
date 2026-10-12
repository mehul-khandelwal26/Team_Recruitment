"""Base extractor interface and extractor registry.

Enables selective registration and execution of signal extractors
without tight coupling to the data ingestion engine.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from app.schemas.ingestion import MemberSchema
from app.signals.schemas import ExtractedSignal, ExtractorDescriptor, SignalStatus


class BaseSignalExtractor(ABC):
    """Abstract contract for all evaluation signal extractors."""

    @property
    @abstractmethod
    def descriptor(self) -> ExtractorDescriptor:
        """Return the metadata descriptor for this extractor."""
        raise NotImplementedError

    def can_extract(self, member: MemberSchema) -> bool:
        """Check whether the member provides the minimum inputs required."""
        for field_name in self.descriptor.required_inputs:
            # Check canonical attributes
            val = getattr(member, field_name, None)
            if val is None:
                # Check custom_fields
                val = member.custom_fields.get(field_name)
            if not val:
                return False
        return True

    @abstractmethod
    def extract(self, member: MemberSchema) -> list[ExtractedSignal]:
        """Produce signals for the given member.

        Must handle errors gracefully and set SignalStatus accordingly.
        """
        raise NotImplementedError


class SignalExtractorRegistry:
    """Registry maintaining available signal extractors."""

    def __init__(self) -> None:
        self._extractors: dict[str, BaseSignalExtractor] = {}

    def register(self, extractor: BaseSignalExtractor) -> None:
        """Register a new extractor."""
        self._extractors[extractor.descriptor.extractor_id] = extractor

    def get(self, extractor_id: str) -> Optional[BaseSignalExtractor]:
        """Retrieve an extractor by ID."""
        return self._extractors.get(extractor_id)

    def list_descriptors(self) -> list[ExtractorDescriptor]:
        """List descriptors of all registered extractors."""
        return [ext.descriptor for ext in self._extractors.values()]

    def get_compatible_extractors(self, available_fields: set[str]) -> list[ExtractorDescriptor]:
        """Return extractors whose required inputs are satisfied by the given fields."""
        compatible = []
        for ext in self._extractors.values():
            if set(ext.descriptor.required_inputs).issubset(available_fields):
                compatible.append(ext.descriptor)
        return compatible
