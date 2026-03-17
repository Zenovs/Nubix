"""
Auto-updater for Nubix.

Checks GitHub Releases API for a newer version, downloads the AppImage,
replaces the current binary, and restarts the application.
"""

from __future__ import annotations

import logging
import os
import stat
import sys
import tempfile
from pathlib import Path
from typing import Optional

import requests
from PySide6.QtCore import QObject, QThread, Signal

from nubix import __version__

logger = logging.getLogger(__name__)

GITHUB_API_URL = "https://api.github.com/repos/Zenovs/Nubix/releases/latest"
ASSET_NAME_PATTERN = "Nubix-{version}-x86_64.AppImage"


def _parse_version(v: str) -> tuple[int, ...]:
    """Convert '1.2.3' to (1, 2, 3) for comparison."""
    try:
        return tuple(int(x) for x in v.lstrip("v").split(".")[:3])
    except Exception:
        return (0,)


def _is_newer(latest: str, current: str) -> bool:
    return _parse_version(latest) > _parse_version(current)


class ReleaseInfo:
    def __init__(self, data: dict):
        self.tag = data.get("tag_name", "")
        self.version = self.tag.lstrip("v")
        self.body = data.get("body", "")
        self.html_url = data.get("html_url", "")
        self.assets: list[dict] = data.get("assets", [])

    def get_appimage_url(self) -> Optional[str]:
        for asset in self.assets:
            name: str = asset.get("name", "")
            if name.endswith(".AppImage"):
                return asset.get("browser_download_url")
        return None

    def get_deb_url(self) -> Optional[str]:
        for asset in self.assets:
            name: str = asset.get("name", "")
            if name.endswith(".deb"):
                return asset.get("browser_download_url")
        return None


class UpdateCheckThread(QThread):
    """Background thread that polls the GitHub releases API."""

    update_available = Signal(object)   # ReleaseInfo
    no_update = Signal()
    check_failed = Signal(str)          # error message

    def run(self):
        try:
            resp = requests.get(
                GITHUB_API_URL,
                headers={"Accept": "application/vnd.github+json"},
                timeout=15,
            )
            resp.raise_for_status()
            info = ReleaseInfo(resp.json())
            if _is_newer(info.version, __version__):
                logger.info("Update available: %s (current: %s)", info.version, __version__)
                self.update_available.emit(info)
            else:
                logger.debug("Already up to date (%s)", __version__)
                self.no_update.emit()
        except requests.RequestException as e:
            logger.warning("Update check failed: %s", e)
            self.check_failed.emit(str(e))


class DownloadThread(QThread):
    """Downloads a file from a URL with progress reporting."""

    progress = Signal(int)      # 0–100
    finished = Signal(str)      # path to downloaded file
    failed = Signal(str)        # error message

    def __init__(self, url: str, dest: Path, parent=None):
        super().__init__(parent)
        self._url = url
        self._dest = dest

    def run(self):
        try:
            resp = requests.get(self._url, stream=True, timeout=60)
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            done = 0
            with open(self._dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        done += len(chunk)
                        if total:
                            self.progress.emit(int(done / total * 100))
            self.finished.emit(str(self._dest))
        except Exception as e:
            logger.error("Download failed: %s", e)
            self.failed.emit(str(e))


class Updater(QObject):
    """
    Manages the full update lifecycle:
    1. check_for_updates() → update_available or no_update signal
    2. download_and_apply(info) → downloads, replaces binary, requests restart
    """

    update_available = Signal(object)   # ReleaseInfo
    no_update = Signal()
    check_failed = Signal(str)
    download_progress = Signal(int)     # 0–100
    download_complete = Signal()
    update_failed = Signal(str)
    restart_required = Signal()         # app should quit and re-exec

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._check_thread: Optional[UpdateCheckThread] = None
        self._download_thread: Optional[DownloadThread] = None
        self._pending_release: Optional[ReleaseInfo] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_for_updates(self) -> None:
        """Start a background check. Non-blocking."""
        if self._check_thread and self._check_thread.isRunning():
            return
        self._check_thread = UpdateCheckThread(self)
        self._check_thread.update_available.connect(self._on_update_available)
        self._check_thread.no_update.connect(self.no_update)
        self._check_thread.check_failed.connect(self.check_failed)
        self._check_thread.start()

    def download_and_apply(self, release: ReleaseInfo) -> None:
        """Download the AppImage for `release` and replace the current binary."""
        url = release.get_appimage_url()
        if not url:
            self.update_failed.emit("No AppImage asset found in this release.")
            return

        current_path = self._current_binary()
        if current_path is None:
            self.update_failed.emit(
                "Cannot determine current binary path. "
                "Please download the update manually."
            )
            return

        dest = Path(tempfile.mkdtemp()) / Path(url).name
        self._download_thread = DownloadThread(url, dest, self)
        self._download_thread.progress.connect(self.download_progress)
        self._download_thread.finished.connect(
            lambda path: self._apply_update(Path(path), current_path)
        )
        self._download_thread.failed.connect(self.update_failed)
        self._download_thread.start()

    @property
    def current_version(self) -> str:
        return __version__

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _on_update_available(self, info: ReleaseInfo):
        self._pending_release = info
        self.update_available.emit(info)

    def _current_binary(self) -> Optional[Path]:
        """Return the path of the running AppImage, or None if not applicable."""
        # When running as AppImage, APPIMAGE env var is set
        appimage = os.environ.get("APPIMAGE")
        if appimage:
            return Path(appimage)

        # When running directly via python (dev mode) — no binary to replace
        if getattr(sys, "frozen", False):
            # PyInstaller bundle
            return Path(sys.executable)

        return None  # Running from source — cannot self-update

    def _apply_update(self, downloaded: Path, current: Path) -> None:
        try:
            # Make the downloaded file executable
            downloaded.chmod(downloaded.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

            # Atomic replace: rename new -> current
            import shutil
            shutil.move(str(downloaded), str(current))
            logger.info("Update applied: %s -> %s", downloaded, current)

            self.download_complete.emit()
            self.restart_required.emit()
        except Exception as e:
            logger.error("Failed to apply update: %s", e)
            self.update_failed.emit(f"Failed to apply update: {e}")
