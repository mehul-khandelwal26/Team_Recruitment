"""In-memory versioned store for eligibility rule configurations.

Guarantees:
- Immutable configuration versions: updates create a new version incrementing the version number.
- Previous versions are preserved unchanged for historical evaluation auditing.
- Pre-populated with default presets (basic, strict, open_solo).
- Small clean interface that can be backed by a relational database later.
"""

from __future__ import annotations

import datetime
from typing import Optional

from app.rules.presets import get_default_presets
from app.rules.schemas import RuleConfiguration, RuleConfigurationUpdate


class RuleConfigStore:
    """Manages versioned rule configurations in memory."""

    def __init__(self) -> None:
        # Map: config_id -> {version_int -> RuleConfiguration}
        self._configs: dict[str, dict[int, RuleConfiguration]] = {}
        self.load_presets()

    def load_presets(self) -> None:
        """Load or reload standard presets."""
        for preset in get_default_presets():
            self._configs.setdefault(preset.config_id, {})[preset.version] = preset

    def reset(self) -> None:
        """Clear store and re-initialize with presets (used in tests)."""
        self._configs.clear()
        self.load_presets()

    def get(self, config_id: str, version: Optional[int] = None) -> Optional[RuleConfiguration]:
        """Retrieve a specific version of a config, or the latest version if version is None."""
        if config_id not in self._configs or not self._configs[config_id]:
            return None

        version_map = self._configs[config_id]
        if version is not None:
            return version_map.get(version)

        # Return latest version
        latest_ver = max(version_map.keys())
        return version_map[latest_ver]

    def list_latest(self, user_id: Optional[str] = None) -> list[RuleConfiguration]:
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

    def save(self, config: RuleConfiguration, user_id: Optional[str] = None) -> RuleConfiguration:
        """Save a new configuration version."""
        now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if not config.created_at:
            config.created_at = now_ts
        config.updated_at = now_ts
        if user_id:
            config.user_id = user_id

        self._configs.setdefault(config.config_id, {})[config.version] = config
        return config

    def update(self, config_id: str, update_payload: RuleConfigurationUpdate) -> Optional[RuleConfiguration]:
        """Update an existing configuration by creating a new immutable version."""
        current = self.get(config_id)
        if current is None:
            return None

        new_version = current.version + 1
        now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Build new configuration object inheriting previous values
        new_config = RuleConfiguration(
            config_id=config_id,
            version=new_version,
            name=update_payload.name if update_payload.name is not None else current.name,
            description=update_payload.description if update_payload.description is not None else current.description,
            global_config=update_payload.global_config if update_payload.global_config is not None else current.global_config.model_copy(deep=True),
            rules=[r.model_copy(deep=True) for r in (update_payload.rules if update_payload.rules is not None else current.rules)],
            is_active=update_payload.is_active if update_payload.is_active is not None else current.is_active,
            created_at=current.created_at,
            updated_at=now_ts,
        )

        self._configs[config_id][new_version] = new_config
        return new_config

    def delete(self, config_id: str) -> bool:
        """Mark a configuration as inactive (soft delete) across all versions."""
        if config_id not in self._configs:
            return False
        for cfg in self._configs[config_id].values():
            cfg.is_active = False
        return True


from app.storage import DelegatingRuleConfigStore

default_config_store = DelegatingRuleConfigStore()
