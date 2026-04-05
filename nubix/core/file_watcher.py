"""
FileWatcher — monitors local sync directories for changes and triggers sync.

Uses the watchdog library (inotify on Linux) to detect file system events.
Changes are debounced: a sync is triggered only after no new events have
arrived for DEBOUNCE_SECONDS, avoiding rapid-fire syncs during bulk writes
(e.g. IDE saves, unzip operations).

Only non-mount remotes are watched — mount-mode remotes write directly
through rclone FUSE and do not need a watcher.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal

logger = logging.getLogger(__name__)

# Seconds of inactivity after the last FS event before triggering a sync
DEBOUNCE_SECONDS = 5


class FileWatcher(QObject):
    """
    Watches local directories and emits sync_needed(remote_id) after changes.

    One watchdog Observer thread is shared across all watched directories.
    Per-remote debounce timers run on the Qt main thread via QTimer.
    """

    sync_needed = Signal(str)  # remote_id

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._observer: Optional[object] = None  # watchdog Observer
        self._watches: dict[str, object] = {}  # remote_id → watchdog watch handle
        self._timers: dict[str, QTimer] = {}  # remote_id → debounce QTimer
        self._paths: dict[str, Path] = {}  # remote_id → local_path
        self._started = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the underlying watchdog observer thread."""
        if self._started:
            return
        try:
            from watchdog.observers import Observer

            self._observer = Observer()
            self._observer.start()
            self._started = True
            logger.info("FileWatcher started")
        except ImportError:
            logger.warning(
                "watchdog not installed — file watching disabled. "
                "Install with: pip install watchdog"
            )

    def stop(self) -> None:
        """Stop the observer and all debounce timers."""
        for timer in self._timers.values():
            timer.stop()
        self._timers.clear()
        if self._observer and self._started:
            try:
                self._observer.stop()
                self._observer.join(timeout=5)
            except Exception as e:
                logger.debug("FileWatcher stop error: %s", e)
            self._started = False
        logger.info("FileWatcher stopped")

    def add_watch(self, remote_id: str, local_path: Path) -> None:
        """Start watching *local_path* for *remote_id*."""
        if not self._started or not self._observer:
            return
        if remote_id in self._watches:
            return  # already watching

        try:
            from watchdog.events import FileSystemEventHandler

            handler = _DebounceHandler(remote_id, self._schedule_sync)
            watch = self._observer.schedule(handler, str(local_path), recursive=True)
            self._watches[remote_id] = watch
            self._paths[remote_id] = local_path
            logger.info("Watching %s for remote %s", local_path, remote_id)
        except Exception as e:
            logger.warning("Could not add watch for %s (%s): %s", remote_id, local_path, e)

    def remove_watch(self, remote_id: str) -> None:
        """Stop watching the directory for *remote_id*."""
        watch = self._watches.pop(remote_id, None)
        if watch and self._observer:
            try:
                self._observer.unschedule(watch)
            except Exception:
                pass
        timer = self._timers.pop(remote_id, None)
        if timer:
            timer.stop()
        self._paths.pop(remote_id, None)
        logger.debug("Removed watch for %s", remote_id)

    def watched_ids(self) -> list[str]:
        return list(self._watches.keys())

    # ------------------------------------------------------------------
    # Internal — called from watchdog handler thread, marshalled to Qt
    # ------------------------------------------------------------------

    def _schedule_sync(self, remote_id: str) -> None:
        """
        Called from the watchdog thread.  Uses a thread-safe Qt mechanism to
        restart the debounce timer on the main thread.
        """
        # QTimer must be started from the main thread; use a zero-ms singleShot
        # which is safe to call from any thread and runs in the main event loop.
        QTimer.singleShot(0, lambda: self._reset_debounce(remote_id))

    def _reset_debounce(self, remote_id: str) -> None:
        """Restart the debounce timer for remote_id (runs on main thread)."""
        if remote_id not in self._timers:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.setInterval(DEBOUNCE_SECONDS * 1000)
            timer.timeout.connect(lambda rid=remote_id: self._fire(rid))
            self._timers[remote_id] = timer
        self._timers[remote_id].start()  # restart resets the countdown

    def _fire(self, remote_id: str) -> None:
        logger.info("Change detected in %s — triggering sync", remote_id)
        self.sync_needed.emit(remote_id)


class _DebounceHandler:
    """Minimal watchdog event handler that calls a callback on any FS event."""

    def __init__(self, remote_id: str, callback):
        self._remote_id = remote_id
        self._callback = callback

    # watchdog calls dispatch() for every event
    def dispatch(self, event) -> None:
        # Ignore directory-only events (directory creation without content)
        # and temporary editor files (e.g. .swp, ~)
        src = getattr(event, "src_path", "")
        if src.endswith((".swp", ".swpx", ".tmp", "~")):
            return
        self._callback(self._remote_id)
