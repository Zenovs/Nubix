"""
FileWatcher — monitors local sync directories for changes and triggers sync.

Uses the watchdog library (inotify on Linux) to detect file system events.
Changes are debounced: a sync is triggered only after no new events have
arrived for DEBOUNCE_SECONDS, avoiding rapid-fire syncs during bulk writes
(e.g. IDE saves, unzip operations).

Only non-mount remotes are watched — mount-mode remotes write directly
through rclone FUSE and do not need a watcher.

Thread safety
-------------
watchdog fires events on its own OS thread.  Qt timers and signals must run
on the Qt main thread.  We bridge the gap with an *internal* Qt signal
(_event_received) whose connection is always a QueuedConnection — Qt
guarantees cross-thread signal delivery via the event loop.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal, Slot

logger = logging.getLogger(__name__)

# Seconds of inactivity after the last FS event before triggering a sync
DEBOUNCE_SECONDS = 5


class FileWatcher(QObject):
    """
    Watches local directories and emits sync_needed(remote_id) after changes.

    One watchdog Observer thread is shared across all watched directories.
    Per-remote debounce timers run on the Qt main thread.
    """

    sync_needed = Signal(str)  # remote_id — emitted after debounce

    # Internal: bridges the watchdog thread → Qt main thread safely.
    # Qt automatically uses QueuedConnection when sender and receiver live
    # on different threads, so this signal is always delivered via the
    # event loop regardless of which thread emits it.
    _event_received = Signal(str)  # remote_id

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._observer: Optional[object] = None  # watchdog Observer
        self._watches: dict[str, object] = {}  # remote_id → watchdog watch handle
        self._timers: dict[str, QTimer] = {}  # remote_id → debounce QTimer
        self._paths: dict[str, Path] = {}  # remote_id → local_path
        self._started = False

        # Connect internal signal to debounce reset — always runs on main thread
        self._event_received.connect(self._reset_debounce)

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
            handler = _DebounceHandler(remote_id, self._on_fs_event)
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
    # Internal
    # ------------------------------------------------------------------

    def _on_fs_event(self, remote_id: str) -> None:
        """Called from the watchdog OS thread — emit signal to cross to Qt thread."""
        self._event_received.emit(remote_id)

    @Slot(str)
    def _reset_debounce(self, remote_id: str) -> None:
        """Restart the debounce timer (always runs on Qt main thread)."""
        if remote_id not in self._timers:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.setInterval(DEBOUNCE_SECONDS * 1000)
            timer.timeout.connect(lambda rid=remote_id: self._fire(rid))
            self._timers[remote_id] = timer
        self._timers[remote_id].start()  # restart resets the countdown

    def _fire(self, remote_id: str) -> None:
        logger.info("File change detected in '%s' — triggering sync", remote_id)
        self.sync_needed.emit(remote_id)


class _DebounceHandler:
    """Watchdog event handler — calls callback on any relevant FS event."""

    # Temp/editor file suffixes to ignore
    _IGNORE = (".swp", ".swpx", ".tmp", ".part", "~")

    def __init__(self, remote_id: str, callback):
        self._remote_id = remote_id
        self._callback = callback

    def dispatch(self, event) -> None:
        src = getattr(event, "src_path", "")
        if any(src.endswith(s) for s in self._IGNORE):
            return
        self._callback(self._remote_id)
