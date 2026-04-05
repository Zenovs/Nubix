"""
MountManager — manages rclone VFS mount subprocesses.

Each mounted remote runs as a long-lived Popen process.  The manager watches
it in a QThread so the UI can react when rclone mount exits unexpectedly.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from nubix.core.rclone_engine import RcloneEngine
from nubix.core.sync_job import JobStatus

logger = logging.getLogger(__name__)


class _MountWatcher(QThread):
    """Waits for a mount process to exit and reports the exit code."""

    exited = Signal(int)  # exit code

    def __init__(self, process: subprocess.Popen, parent=None):
        super().__init__(parent)
        self._process = process

    def run(self):
        code = self._process.wait()
        self.exited.emit(code)


class MountManager(QObject):
    """Owns and monitors all active rclone mount processes."""

    mount_status_changed = Signal(str, str)  # remote_id, JobStatus value
    mount_failed = Signal(str, str)  # remote_id, error message

    def __init__(self, engine: RcloneEngine, parent: QObject | None = None):
        super().__init__(parent)
        self._engine = engine
        # remote_id → (Popen, _MountWatcher, mountpoint)
        self._mounts: dict[str, tuple[subprocess.Popen, _MountWatcher, Path]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def mount(
        self,
        remote_id: str,
        remote_path: str,
        mountpoint: Path,
        cache_mode: str = "full",
        cache_size: str = "1G",
    ) -> None:
        """Start a VFS mount for *remote_id*. No-op if already mounted."""
        if remote_id in self._mounts:
            logger.debug("Mount already active for %s", remote_id)
            return

        # Clean up any stale FUSE mount left by a previous crashed process.
        # "Transport endpoint is not connected" occurs when the mountpoint
        # directory exists but the backing rclone process is gone.
        # fusermount3 -u -z performs a lazy unmount that handles this case.
        self._cleanup_stale_mount(mountpoint)

        try:
            proc = self._engine.start_mount(
                remote_id, remote_path, mountpoint, cache_mode, cache_size
            )
        except Exception as e:
            logger.error("Failed to start mount for %s: %s", remote_id, e)
            self.mount_failed.emit(remote_id, str(e))
            return

        watcher = _MountWatcher(proc)
        watcher.exited.connect(lambda code, rid=remote_id: self._on_exited(rid, code))
        watcher.start()

        self._mounts[remote_id] = (proc, watcher, mountpoint)
        self._emit_status(remote_id, JobStatus.MOUNTED)
        logger.info("Mount started for %s at %s", remote_id, mountpoint)

    def unmount(self, remote_id: str) -> None:
        """Unmount and clean up for *remote_id*."""
        entry = self._mounts.pop(remote_id, None)
        if not entry:
            return
        proc, watcher, mountpoint = entry

        # Try FUSE unmount first; fall back to terminating the process
        if not self._engine.unmount(mountpoint):
            logger.warning("fusermount failed for %s — terminating process", remote_id)
            try:
                proc.terminate()
            except ProcessLookupError:
                pass

        watcher.quit()
        self._emit_status(remote_id, JobStatus.IDLE)
        logger.info("Unmounted %s", remote_id)

    def unmount_all(self) -> None:
        for remote_id in list(self._mounts.keys()):
            self.unmount(remote_id)

    def is_mounted(self, remote_id: str) -> bool:
        return remote_id in self._mounts

    def mounted_ids(self) -> list[str]:
        return list(self._mounts.keys())

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _on_exited(self, remote_id: str, exit_code: int) -> None:
        """Called when the rclone mount process exits unexpectedly."""
        if remote_id not in self._mounts:
            return  # already cleaned up via unmount()
        _, _, mountpoint = self._mounts.pop(remote_id)
        logger.warning("Mount for %s exited with code %d", remote_id, exit_code)
        if exit_code != 0:
            self.mount_failed.emit(remote_id, f"rclone mount exited with code {exit_code}")
        self._emit_status(remote_id, JobStatus.IDLE)

    def _cleanup_stale_mount(self, mountpoint: Path) -> None:
        """Remove a stale/zombie FUSE mount if present.

        A stale mount shows as "Transport endpoint is not connected" when
        the rclone process that backed it has died.  A lazy unmount (-z)
        detaches the mountpoint immediately even if the process is gone.
        """
        import shutil

        for binary in ("fusermount3", "fusermount"):
            found = shutil.which(binary)
            if not found:
                continue
            result = subprocess.run(
                [found, "-u", "-z", str(mountpoint)],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                logger.info("Cleaned up stale mount at %s", mountpoint)
            # returncode != 0 just means nothing was mounted there — that's fine
            return  # only need one tool

    def _emit_status(self, remote_id: str, status: JobStatus) -> None:
        self.mount_status_changed.emit(remote_id, status.value)
