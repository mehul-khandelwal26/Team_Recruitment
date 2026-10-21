"""In-memory versioned store for scoring configurations.

Guarantees:
- Immutable configuration versions: updates create a new version incrementing the version number.
- Previous versions are preserved unchanged for historical score reproducibility.
- Pre-populated with default presets (balanced, technical_heavy, academic_heavy).
"""

from __future__ import annotations

import datetime
from typing import Optional

from app.scoring.presets import get_default_scoring_presets
from app.scoring.schemas import ScoringConfiguration, ScoringConfigurationUpdate


class ScoringConfigStore:
    """Manages versioned scoring configurations in memory."""

    def __init__(self) -> None:
        # Map: config_id -> {version_int -> ScoringConfiguration}
        self._configs: dict[str, dict[int, ScoringConfiguration]] = {}
        self.load_presets()

    def load_presets(self) -> None:
        """Load standard default presets."""
        for preset in get_default_scoring_presets():
            self._configs.setdefault(preset.config_id, {})[preset.version] = preset

    def reset(self) -> None:
        """Clear store and reload presets (used in tests)."""
        self._configs.clear()
        self.load_presets()

    def get(self, config_id: str, version: Optional[int] = None) -> Optional[ScoringConfiguration]:
        """Retrieve a specific version of a config, or latest if version is None."""
        if config_id not in self._configs or not self._configs[config_id]:
            return None

        ver_map = self._configs[config_id]
        if version is not None:
            return ver_map.get(version)

        latest_ver = max(ver_map.keys())
        return ver_map[latest_ver]

    def list_latest(self, user_id: Optional[str] = None) -> list[ScoringConfiguration]:
        """Return the latest version of every active configuration, filtered by user if provided."""
        results = []
        for config_id, ver_map in self._configs.items():
            if ver_map:
                latest_ver = max(ver_map.keys())
                cfg = ver_map[latest_ver]
                if cfg.is_active:
                    if user_id:
                        cfg_uid = getattr(cfg, "user_id", None)
                        if cfg_uid is not None and cfg_uid != "system" and cfg_uid != user_id:
                            continue
                    results.append(cfg)
        return results

    def list_versions(self, config_id: str) -> list[int]:
        """List all version numbers available for a given config_id."""
        if config_id not in self._configs:
            return []
        return sorted(self._configs[config_id].keys())

    def save(self, config: ScoringConfiguration, user_id: Optional[str] = None) -> ScoringConfiguration:
        """Save a new configuration version."""
        now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if not config.created_at:
            config.created_at = now_ts
        config.updated_at = now_ts
        if user_id:
            config.user_id = user_id

        self._configs.setdefault(config.config_id, {})[config.version] = config
        return config

    def update(self, config_id: str, update_payload: ScoringConfigurationUpdate) -> Optional[ScoringConfiguration]:
        """Update an existing configuration by creating a new immutable version."""
        current = self.get(config_id)
        if current is None:
            return None

        new_version = current.version + 1
        now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

        new_config = ScoringConfiguration(
            config_id=config_id,
            version=new_version,
            name=update_payload.name if update_payload.name is not None else current.name,
            description=update_payload.description if update_payload.description is not None else current.description,
            criteria=[c.model_copy(deep=True) for c in (update_payload.criteria if update_payload.criteria is not None else current.criteria)],
            scale_max=update_payload.scale_max if update_payload.scale_max is not None else current.scale_max,
            lead_field=update_payload.lead_field if update_payload.lead_field is not None else current.lead_field,
            lead_values=list(update_payload.lead_values) if update_payload.lead_values is not None else list(current.lead_values),
            score_ineligible_teams=update_payload.score_ineligible_teams if update_payload.score_ineligible_teams is not None else current.score_ineligible_teams,
            is_active=update_payload.is_active if update_payload.is_active is not None else current.is_active,
            created_at=current.created_at,
            updated_at=now_ts,
        )

        self._configs[config_id][new_version] = new_config
        return new_config

    def delete(self, config_id: str) -> bool:
        """Mark all versions of a configuration as inactive (soft delete)."""
        if config_id not in self._configs or not self._configs[config_id]:
            return False
        for cfg in self._configs[config_id].values():
            cfg.is_active = False
        return True


from app.storage import DelegatingScoringConfigStore

default_scoring_config_store = DelegatingScoringConfigStore()
