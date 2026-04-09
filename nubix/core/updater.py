"""
Auto-updater for Nubix.

Checks GitHub Releases API for a newer version, then either:
  - downloads the AppImage and replaces the binary (AppImage installs), or
  - runs `git pull` to update the source tree (source/dev installs).
"""

from __future__ import annotations

import logging
import os
import stat
import subprocess
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

    update_available = Signal(object)  # ReleaseInfo
    no_update = Signal()
    check_failed = Signal(str)  # error message

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


class GitPullThread(QThread):
    """Updates source install via git fetch+reset, or tarball if no .git exists."""

    pull_done = Signal()
    pull_failed = Signal(str)

    def __init__(self, repo_dir: Path, parent=None):
        super().__init__(parent)
        self._repo_dir = repo_dir

    def run(self):
        if (self._repo_dir / ".git").exists():
            self._update_via_git()
        else:
            self._update_via_tarball()

    def _update_via_git(self):
        try:
            fetch = subprocess.run(
                ["git", "fetch", "--depth=1", "origin", "main"],
                cwd=self._repo_dir,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if fetch.returncode != 0:
                msg = (fetch.stderr or fetch.stdout).strip()
                logger.error("git fetch failed: %s", msg)
                self.pull_failed.emit(f"git fetch failed: {msg}")
                return

            reset = subprocess.run(
                ["git", "reset", "--hard", "origin/main"],
                cwd=self._repo_dir,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if reset.returncode == 0:
                logger.info("git update succeeded: %s", reset.stdout.strip())
                self.pull_done.emit()
            else:
                msg = (reset.stderr or reset.stdout).strip()
                logger.error("git reset failed: %s", msg)
                self.pull_failed.emit(msg)
        except FileNotFoundError:
            self.pull_failed.emit("git not found. Install it with: sudo apt install git")
        except Exception as e:
            self.pull_failed.emit(str(e))

    def _update_via_tarball(self):
        """Download source tarball from GitHub and extract over install dir."""
        import shutil
        import tarfile
        import tempfile

        url = "https://github.com/Zenovs/Nubix/archive/refs/heads/main.tar.gz"
        try:
            logger.info("No .git found — updating via tarball from %s", url)
            resp = requests.get(url, stream=True, timeout=60)
            resp.raise_for_status()

            with tempfile.TemporaryDirectory() as tmp:
                archive = Path(tmp) / "nubix.tar.gz"
                with open(archive, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)

                with tarfile.open(archive, "r:gz") as tar:
                    tar.extractall(tmp)

                # GitHub names the extracted folder "Nubix-main"
                extracted = next(Path(tmp).glob("Nubix-*"), None)
                if not extracted or not extracted.is_dir():
                    self.pull_failed.emit("Could not find extracted source in tarball")
                    return

                # Copy all source files, skip .venv and .git
                skip = {".venv", ".git"}
                for item in extracted.iterdir():
                    if item.name in skip:
                        continue
                    dst = self._repo_dir / item.name
                    if item.is_dir():
                        if dst.exists():
                            shutil.rmtree(dst)
                        shutil.copytree(item, dst)
                    else:
                        shutil.copy2(item, dst)

            logger.info("Tarball update complete")
            self.pull_done.emit()
        except Exception as e:
            logger.error("Tarball update failed: %s", e)
            self.pull_failed.emit(str(e))


class DownloadThread(QThread):
    """Downloads a file from a URL with progress reporting."""

    progress = Signal(int)  # 0–100
    finished = Signal(str)  # path to downloaded file
    failed = Signal(str)  # error message

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

    update_available = Signal(object)  # ReleaseInfo
    no_update = Signal()
    check_failed = Signal(str)
    download_progress = Signal(int)  # 0–100
    download_complete = Signal()
    update_failed = Signal(str)
    restart_required = Signal()  # app should quit and re-exec

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._check_thread: Optional[UpdateCheckThread] = None
        self._download_thread: Optional[DownloadThread] = None
        self._git_thread: Optional[GitPullThread] = None
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
        """Update Nubix to `release`.

        Strategy:
        1. AppImage install  → download new AppImage, replace binary, restart.
        2. Source install    → git pull in the repo directory, restart.
        """
        # ── Source install: use git pull ──────────────────────────────────────
        repo_dir = self._source_repo_dir()
        if repo_dir is not None:
            logger.info("Source install detected — running git pull in %s", repo_dir)
            self._git_thread = GitPullThread(repo_dir, self)
            self._git_thread.pull_done.connect(self._on_git_pull_done)
            self._git_thread.pull_failed.connect(self.update_failed)
            self._git_thread.start()
            return

        # ── AppImage install: download new binary ─────────────────────────────
        url = release.get_appimage_url()
        if not url:
            self.update_failed.emit(
                "No AppImage asset found in this release.\n"
                "Update manually: https://github.com/Zenovs/Nubix/releases"
            )
            return

        current_path = self._current_binary()
        if current_path is None:
            self.update_failed.emit(
                "Cannot determine current binary path. " "Please download the update manually."
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

    def _on_git_pull_done(self) -> None:
        logger.info("git pull complete — signalling restart")
        self.download_complete.emit()
        self.restart_required.emit()

    @property
    def current_version(self) -> str:
        return __version__

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _on_update_available(self, info: ReleaseInfo):
        self._pending_release = info
        self.update_available.emit(info)

    def _source_repo_dir(self) -> Optional[Path]:
        """Return the source install directory, or None if running as AppImage/bundle."""
        if os.environ.get("APPIMAGE") or getattr(sys, "frozen", False):
            return None

        # Walk up from this file to find .git directory (git clone installs)
        candidate = Path(__file__).resolve().parent
        for _ in range(6):
            if (candidate / ".git").exists():
                return candidate
            candidate = candidate.parent

        # Fallback: standard install location created by install.sh (no .git)
        standard = Path.home() / ".local" / "share" / "nubix"
        if standard.exists() and (standard / "main.py").exists():
            return standard

        return None

    def _current_binary(self) -> Optional[Path]:
        """Return the path of the running AppImage, or None if not applicable."""
        appimage = os.environ.get("APPIMAGE")
        if appimage:
            return Path(appimage)
        if getattr(sys, "frozen", False):
            return Path(sys.executable)
        return None

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
