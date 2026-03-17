"""Configuration manager for Nubix."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from PySide6.QtCore import QObject, Signal

from nubix.constants import (
    CONFIG_DIR,
    GLOBAL_CONFIG_FILE,
    REMOTES_DIR,
    RCLONE_CONFIG_DIR,
    LOG_DIR,
    CACHE_DIR,
    DEFAULT_BANDWIDTH_LIMIT,
    DEFAULT_LOG_RETENTION_DAYS,
    DEFAULT_SYNC_INTERVAL_MINUTES,
)
from nubix.exceptions import ConfigValidationError

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG: dict[str, Any] = {
    "general": {
        "autostart": False,
        "minimize_to_tray": True,
        "notifications": "errors_only",  # "all" | "errors_only" | "none"
        "rclone_binary": "",  # empty = auto-detect
        "log_retention_days": DEFAULT_LOG_RETENTION_DAYS,
        "sync_interval_minutes": DEFAULT_SYNC_INTERVAL_MINUTES,
    },
    "bandwidth": {
        "upload_limit": DEFAULT_BANDWIDTH_LIMIT,
        "download_limit": DEFAULT_BANDWIDTH_LIMIT,
        "time_rules": [],
    },
    "ui": {
        "theme": "auto",  # "light" | "dark" | "auto"
        "window_geometry": None,
    },
}


class ConfigManager(QObject):
    """Reads and writes Nubix configuration files."""

    config_changed = Signal(str, object)  # key_path, new_value

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._config: dict[str, Any] = {}
        self._ensure_dirs()
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key_path: str, default: Any = None) -> Any:
        """Get a config value using dot-separated key path, e.g. 'general.autostart'."""
        keys = key_path.split(".")
        node = self._config
        for k in keys:
            if not isinstance(node, dict) or k not in node:
                return default
            node = node[k]
        return node

    def set(self, key_path: str, value: Any) -> None:
        """Set a config value and persist it."""
        keys = key_path.split(".")
        node = self._config
        for k in keys[:-1]:
            node = node.setdefault(k, {})
        node[keys[-1]] = value
        self._save()
        self.config_changed.emit(key_path, value)

    def get_remote_config(self, remote_id: str) -> dict | None:
        """Load the YAML config for a specific remote."""
        path = REMOTES_DIR / f"{remote_id}.yaml"
        if not path.exists():
            return None
        try:
            with open(path) as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error("Failed to load remote config %s: %s", remote_id, e)
            return None

    def save_remote_config(self, remote_id: str, data: dict) -> None:
        """Persist a remote's configuration."""
        REMOTES_DIR.mkdir(parents=True, exist_ok=True)
        path = REMOTES_DIR / f"{remote_id}.yaml"
        with open(path, "w") as f:
            yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)
        logger.debug("Saved remote config: %s", remote_id)

    def delete_remote_config(self, remote_id: str) -> None:
        """Remove a remote's configuration file."""
        path = REMOTES_DIR / f"{remote_id}.yaml"
        if path.exists():
            path.unlink()

    def list_remote_ids(self) -> list[str]:
        """Return all configured remote IDs."""
        if not REMOTES_DIR.exists():
            return []
        return [p.stem for p in REMOTES_DIR.glob("*.yaml")]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ensure_dirs(self) -> None:
        for d in [CONFIG_DIR, REMOTES_DIR, RCLONE_CONFIG_DIR, LOG_DIR, CACHE_DIR]:
            d.mkdir(parents=True, exist_ok=True)

    def _load(self) -> None:
        if GLOBAL_CONFIG_FILE.exists():
            try:
                with open(GLOBAL_CONFIG_FILE) as f:
                    loaded = yaml.safe_load(f) or {}
                self._config = self._deep_merge(_DEFAULT_CONFIG.copy(), loaded)
                logger.debug("Loaded config from %s", GLOBAL_CONFIG_FILE)
            except Exception as e:
                logger.error("Failed to load config: %s — using defaults", e)
                self._config = _DEFAULT_CONFIG.copy()
        else:
            self._config = _DEFAULT_CONFIG.copy()
            self._save()

    def _save(self) -> None:
        try:
            with open(GLOBAL_CONFIG_FILE, "w") as f:
                yaml.safe_dump(self._config, f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            logger.error("Failed to save config: %s", e)

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConfigManager._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
