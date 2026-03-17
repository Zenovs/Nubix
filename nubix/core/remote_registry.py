"""
Remote registry — manages configured cloud connections.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Optional

from PySide6.QtCore import QObject, Signal

from nubix.core.config_manager import ConfigManager
from nubix.core.credential_vault import CredentialVault
from nubix.core.sync_job import SyncJob, SyncMode
from nubix.exceptions import RemoteNotConfiguredError

logger = logging.getLogger(__name__)


@dataclass
class RemoteConfig:
    remote_id: str
    display_name: str
    provider_type: str
    local_path: str
    remote_path: str
    sync_mode: SyncMode = SyncMode.FULL
    is_enabled: bool = True
    filters: list[str] = field(default_factory=list)
    bandwidth_limit: str = "0"
    is_scheduled: bool = False

    def to_dict(self) -> dict:
        return {
            "remote_id": self.remote_id,
            "display_name": self.display_name,
            "provider_type": self.provider_type,
            "local_path": self.local_path,
            "remote_path": self.remote_path,
            "sync_mode": self.sync_mode.value,
            "is_enabled": self.is_enabled,
            "filters": self.filters,
            "bandwidth_limit": self.bandwidth_limit,
            "is_scheduled": self.is_scheduled,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RemoteConfig":
        return cls(
            remote_id=data["remote_id"],
            display_name=data.get("display_name", data["remote_id"]),
            provider_type=data["provider_type"],
            local_path=data["local_path"],
            remote_path=data.get("remote_path", ""),
            sync_mode=SyncMode(data.get("sync_mode", "full")),
            is_enabled=data.get("is_enabled", True),
            filters=data.get("filters", []),
            bandwidth_limit=data.get("bandwidth_limit", "0"),
            is_scheduled=data.get("is_scheduled", False),
        )

    def to_sync_job(self) -> SyncJob:
        from pathlib import Path
        return SyncJob(
            remote_id=self.remote_id,
            provider_type=self.provider_type,
            local_path=Path(self.local_path),
            remote_path=self.remote_path,
            sync_mode=self.sync_mode,
            filters=self.filters,
            bandwidth_limit=self.bandwidth_limit,
            is_scheduled=self.is_scheduled,
        )


class RemoteRegistry(QObject):
    """Maintains the list of configured remotes."""

    remote_added = Signal(object)    # RemoteConfig
    remote_removed = Signal(str)     # remote_id
    remote_updated = Signal(object)  # RemoteConfig

    def __init__(self, config: ConfigManager, vault: CredentialVault, parent: QObject | None = None):
        super().__init__(parent)
        self._config = config
        self._vault = vault
        self._remotes: dict[str, RemoteConfig] = {}
        self._load_all()

    def add_remote(self, data: dict) -> RemoteConfig:
        """Add and persist a new remote. Generates remote_id if not provided."""
        if "remote_id" not in data:
            data["remote_id"] = str(uuid.uuid4())[:8]
        rc = RemoteConfig.from_dict(data)
        self._remotes[rc.remote_id] = rc
        self._config.save_remote_config(rc.remote_id, rc.to_dict())
        self.remote_added.emit(rc)
        logger.info("Remote added: %s (%s)", rc.remote_id, rc.provider_type)
        return rc

    def remove_remote(self, remote_id: str) -> None:
        """Remove a remote and its credentials."""
        if remote_id not in self._remotes:
            raise RemoteNotConfiguredError(remote_id)
        del self._remotes[remote_id]
        self._config.delete_remote_config(remote_id)
        self._vault.delete_all(remote_id)
        self.remote_removed.emit(remote_id)
        logger.info("Remote removed: %s", remote_id)

    def update_remote(self, remote_id: str, data: dict) -> RemoteConfig:
        if remote_id not in self._remotes:
            raise RemoteNotConfiguredError(remote_id)
        data["remote_id"] = remote_id
        rc = RemoteConfig.from_dict(data)
        self._remotes[remote_id] = rc
        self._config.save_remote_config(remote_id, rc.to_dict())
        self.remote_updated.emit(rc)
        return rc

    def get_remote(self, remote_id: str) -> RemoteConfig:
        if remote_id not in self._remotes:
            raise RemoteNotConfiguredError(remote_id)
        return self._remotes[remote_id]

    def list_remotes(self) -> list[RemoteConfig]:
        return list(self._remotes.values())

    def _load_all(self) -> None:
        for remote_id in self._config.list_remote_ids():
            data = self._config.get_remote_config(remote_id)
            if data:
                try:
                    rc = RemoteConfig.from_dict(data)
                    self._remotes[rc.remote_id] = rc
                except Exception as e:
                    logger.error("Failed to load remote %s: %s", remote_id, e)
