"""Base extractor interface and extractor registry.

Enables selective registration, category management, and execution of signal extractors
without tight coupling to the data ingestion engine or premature scoring calculation.
"""

from __future__ import annotations

import datetime
import uuid
from abc import ABC, abstractmethod
from typing import Any, Optional

from app.schemas.ingestion import MemberSchema, TeamSchema
from app.signals.schemas import (
    CategoryDefinition,
    ExtractedSignal,
    ExtractionRunResponse,
    ExtractorDescriptor,
    MemberExtractionResult,
    SignalCatalogResponse,
    SignalDefinition,
    SignalEvidence,
    SignalStatus,
    TeamExtractionResult,
)


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

    def validate_inputs(self, member: MemberSchema) -> tuple[bool, Optional[str]]:
        """Validate whether member has the necessary inputs.

        Returns (is_valid, failure_reason).
        """
        for field_name in self.descriptor.required_inputs:
            val = getattr(member, field_name, None)
            if val is None:
                val = member.custom_fields.get(field_name)
            if val is None or (isinstance(val, str) and not val.strip()):
                return False, f"Missing required input '{field_name}'"
        return True, None

    def supports_signal(self, signal_key: str) -> bool:
        """Check if this extractor produces the specified signal key."""
        return signal_key in self.descriptor.produced_signals

    @abstractmethod
    def extract(
        self,
        member: MemberSchema,
        selected_signals: Optional[set[str]] = None,
        config: Optional[dict[str, Any]] = None,
    ) -> list[ExtractedSignal]:
        """Produce signals for the given member.

        Args:
            member: Member data schema.
            selected_signals: Subset of signal keys to extract. If None, extract all.
            config: Optional extractor-specific configuration dictionary.

        Must handle errors gracefully and set SignalStatus accordingly.
        """
        raise NotImplementedError


class SignalExtractorRegistry:
    """Registry maintaining available signal extractors and categories."""

    def __init__(self) -> None:
        self._extractors: dict[str, BaseSignalExtractor] = {}
        self._categories: dict[str, CategoryDefinition] = {}

    def register(self, extractor: BaseSignalExtractor) -> None:
        """Register a new extractor and automatically register its category."""
        desc = extractor.descriptor
        self._extractors[desc.extractor_id] = extractor

        # Track category
        cat_id = desc.category
        if cat_id not in self._categories:
            self._categories[cat_id] = CategoryDefinition(
                category_id=cat_id,
                name=cat_id.capitalize(),
                description=f"{cat_id.capitalize()} evaluation signals",
                signal_keys=list(desc.produced_signals),
            )
        else:
            cat = self._categories[cat_id]
            for sig in desc.produced_signals:
                if sig not in cat.signal_keys:
                    cat.signal_keys.append(sig)

    def register_category(self, category: CategoryDefinition) -> None:
        """Register or override a category definition with rich metadata."""
        self._categories[category.category_id] = category

    def get(self, extractor_id: str) -> Optional[BaseSignalExtractor]:
        """Retrieve an extractor by ID."""
        return self._extractors.get(extractor_id)

    def list_extractors(self) -> list[BaseSignalExtractor]:
        """List all registered extractor instances."""
        return list(self._extractors.values())

    def list_descriptors(self) -> list[ExtractorDescriptor]:
        """List descriptors of all registered extractors."""
        return [ext.descriptor for ext in self._extractors.values()]

    def list_categories(self) -> list[CategoryDefinition]:
        """List all known categories."""
        return list(self._categories.values())

    def list_signals(self) -> list[SignalDefinition]:
        """List all supported individual signals across registered extractors."""
        all_signals: list[SignalDefinition] = []
        seen_keys: set[str] = set()

        for ext in self._extractors.values():
            desc = ext.descriptor
            if desc.signals:
                for sig in desc.signals:
                    if sig.signal_key not in seen_keys:
                        all_signals.append(sig)
                        seen_keys.add(sig.signal_key)
            else:
                for sig_key in desc.produced_signals:
                    if sig_key not in seen_keys:
                        all_signals.append(
                            SignalDefinition(
                                signal_key=sig_key,
                                name=sig_key.replace("_", " ").title(),
                                description=f"Signal {sig_key} from {desc.name}",
                                category=desc.category,
                                value_type="string",
                            )
                        )
                        seen_keys.add(sig_key)
        return all_signals

    def get_catalog(self) -> SignalCatalogResponse:
        """Produce a complete catalog of categories, analyzers, and signals."""
        return SignalCatalogResponse(
            categories=self.list_categories(),
            analyzers=self.list_descriptors(),
            signals=self.list_signals(),
        )

    def get_compatible_extractors(self, available_fields: set[str]) -> list[ExtractorDescriptor]:
        """Return extractors whose required inputs are satisfied by the given fields."""
        compatible = []
        for ext in self._extractors.values():
            if set(ext.descriptor.required_inputs).issubset(available_fields):
                compatible.append(ext.descriptor)
        return compatible

    def get_extractor_for_signal(self, signal_key: str) -> Optional[BaseSignalExtractor]:
        """Find the extractor registered to produce a given signal key."""
        for ext in self._extractors.values():
            if signal_key in ext.descriptor.produced_signals:
                return ext
        return None

    def execute_extraction(
        self,
        teams: list[TeamSchema | dict[str, Any]],
        selected_signals: Optional[list[str]] = None,
        config: Optional[dict[str, Any]] = None,
    ) -> ExtractionRunResponse:
        """Execute signal extraction for multiple teams and members.

        Respects selective signal execution: only selected analyzers and signals run.
        Preserves team and member associations.
        Handles individual failures gracefully without aborting unrelated analyses.
        """
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        run_config = config or {}
        warnings: list[str] = []
        errors: list[str] = []

        # Convert dict teams to TeamSchema if needed
        validated_teams: list[TeamSchema] = []
        for t in teams:
            if isinstance(t, TeamSchema):
                validated_teams.append(t)
            elif isinstance(t, dict):
                try:
                    validated_teams.append(TeamSchema.model_validate(t))
                except Exception as exc:
                    errors.append(f"Invalid team structure: {exc}")
            else:
                errors.append(f"Unsupported team type: {type(t)}")

        # Determine all available signals if not specified
        all_available_signals = [s.signal_key for s in self.list_signals()]
        if selected_signals is None:
            active_signals = all_available_signals
        else:
            active_signals = [s.strip() for s in selected_signals if s and s.strip()]

        # Map active signals to their respective extractors
        extractor_to_signals: dict[BaseSignalExtractor, set[str]] = {}
        unsupported_signals: list[str] = []

        for sig_key in active_signals:
            ext = self.get_extractor_for_signal(sig_key)
            if ext:
                extractor_to_signals.setdefault(ext, set()).add(sig_key)
            elif sig_key.startswith("custom:") or sig_key.startswith("custom_"):
                # Dynamically resolved custom recruitment signal from registration data
                pass
            else:
                unsupported_signals.append(sig_key)

        if unsupported_signals:
            warning_msg = f"Requested unsupported or unregistered signals: {unsupported_signals}"
            warnings.append(warning_msg)

        analyzers_executed = [ext.descriptor.extractor_id for ext in extractor_to_signals.keys()]
        if any(s.startswith("custom:") or s.startswith("custom_") for s in active_signals):
            analyzers_executed.append("custom_field_extractor")

        team_results: list[TeamExtractionResult] = []
        total_members = 0

        for team in validated_teams:
            member_results: list[MemberExtractionResult] = []
            for member in team.members:
                total_members += 1
                member_signals: list[ExtractedSignal] = []

                # Run each relevant extractor
                for extractor, sigs in extractor_to_signals.items():
                    try:
                        extracted = extractor.extract(
                            member=member,
                            selected_signals=sigs,
                            config=run_config,
                        )
                        member_signals.extend(extracted)
                    except Exception as exc:
                        # Defensive boundary: analyzer crash must never abort extraction
                        err_msg = f"Extractor '{extractor.descriptor.extractor_id}' failed unexpectedly: {exc}"
                        errors.append(err_msg)
                        for s_key in sigs:
                            member_signals.append(
                                ExtractedSignal(
                                    signal_key=s_key,
                                    category=extractor.descriptor.category,
                                    status=SignalStatus.FAILED,
                                    error_message=f"Analyzer internal error: {exc}",
                                )
                            )

                # Extract requested custom signals and mapped custom fields from member data
                custom_keys_to_extract = set(
                    [s for s in active_signals if s.startswith("custom:") or s.startswith("custom_")]
                )
                for k in member.custom_fields.keys():
                    if k.startswith("custom:"):
                        custom_keys_to_extract.add(k)

                for sig_key in custom_keys_to_extract:
                    raw_k = sig_key.split(":", 1)[1] if ":" in sig_key else sig_key[7:]
                    val = (
                        member.custom_fields.get(sig_key)
                        or member.custom_fields.get(raw_k)
                        or member.raw_data.get(raw_k)
                        or member.raw_data.get(sig_key)
                    )
                    if val is not None and not (isinstance(val, str) and not val.strip()):
                        member_signals.append(
                            ExtractedSignal(
                                signal_key=sig_key,
                                category="custom",
                                status=SignalStatus.EXTRACTED,
                                value=val,
                                evidence=SignalEvidence(
                                    source="registration_custom_field", confidence=0.85
                                ),
                            )
                        )
                    else:
                        member_signals.append(
                            ExtractedSignal(
                                signal_key=sig_key,
                                category="custom",
                                status=SignalStatus.NOT_APPLICABLE,
                                value=None,
                                evidence=SignalEvidence(
                                    source="registration_custom_field", confidence=0.0
                                ),
                            )
                        )

                # Append results for unsupported signals
                for unsupp in unsupported_signals:
                    member_signals.append(
                        ExtractedSignal(
                            signal_key=unsupp,
                            category="unknown",
                            status=SignalStatus.FAILED,
                            error_message=f"Signal '{unsupp}' is not supported by any registered extractor.",
                        )
                    )

                member_results.append(
                    MemberExtractionResult(
                        member_id=member.member_id,
                        name=member.name,
                        signals=member_signals,
                    )
                )

            team_results.append(
                TeamExtractionResult(
                    team_id=team.team_id,
                    team_name=team.team_name,
                    is_temporary_id=getattr(team, "is_temporary_id", False),
                    is_unresolved=getattr(team, "is_unresolved", False),
                    member_results=member_results,
                )
            )

        return ExtractionRunResponse(
            run_id=run_id,
            teams=team_results,
            selected_signals=active_signals,
            analyzers_executed=analyzers_executed,
            total_teams=len(validated_teams),
            total_members=total_members,
            warnings=warnings,
            errors=errors,
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
