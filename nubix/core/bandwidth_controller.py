"""Bandwidth controller for throttling rclone transfers."""

from __future__ import annotations

import logging
import re

from PySide6.QtCore import QObject, Signal

from nubix.core.config_manager import ConfigManager

logger = logging.getLogger(__name__)


def mbps_to_rclone(mbps: float) -> str:
    """Convert megabytes/sec float to rclone bwlimit string."""
    if mbps <= 0:
        return "0"
    if mbps >= 1:
        return f"{mbps:.0f}M"
    kb = mbps * 1024
    return f"{kb:.0f}k"


def rclone_to_mbps(limit_str: str) -> float:
    """Convert rclone bwlimit string to MB/s float."""
    if not limit_str or limit_str == "0":
        return 0.0
    m = re.match(r"([0-9.]+)\s*([kKmMgG])?", limit_str.strip())
    if not m:
        return 0.0
    value = float(m.group(1))
    unit = (m.group(2) or "").upper()
    if unit == "K":
        return value / 1024
    elif unit == "M":
        return value
    elif unit == "G":
        return value * 1024
    return value


def format_for_display(limit_str: str) -> str:
    """Convert rclone limit string to human-readable label."""
    if not limit_str or limit_str == "0":
        return "Unlimited"
    mbps = rclone_to_mbps(limit_str)
    if mbps < 1:
        return f"{mbps * 1024:.0f} KB/s"
    return f"{mbps:.1f} MB/s"


class BandwidthController(QObject):
    """Manages upload/download bandwidth limits."""

    limits_changed = Signal(str, str)  # upload_limit, download_limit

    def __init__(self, config: ConfigManager, parent: QObject | None = None):
        super().__init__(parent)
        self._config = config

    @property
    def upload_limit(self) -> str:
        return self._config.get("bandwidth.upload_limit", "0")

    @property
    def download_limit(self) -> str:
        return self._config.get("bandwidth.download_limit", "0")

    def set_upload_limit(self, limit_str: str) -> None:
        self._config.set("bandwidth.upload_limit", limit_str)
        self.limits_changed.emit(self.upload_limit, self.download_limit)
        logger.debug("Upload limit set to %s", limit_str)

    def set_download_limit(self, limit_str: str) -> None:
        self._config.set("bandwidth.download_limit", limit_str)
        self.limits_changed.emit(self.upload_limit, self.download_limit)
        logger.debug("Download limit set to %s", limit_str)

    def get_combined_limit(self) -> str:
        """Return combined bwlimit string for rclone (upload:download)."""
        ul = self.upload_limit
        dl = self.download_limit
        if ul == "0" and dl == "0":
            return "0"
        return f"{ul}:{dl}"
