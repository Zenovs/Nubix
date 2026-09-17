"""
NubixApp — wires all subsystems together and manages application lifecycle.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from nubix.core.bandwidth_controller import BandwidthController
from nubix.core.config_manager import ConfigManager
from nubix.core.credential_vault import CredentialVault
from nubix.core.file_watcher import FileWatcher
from nubix.core.mount_manager import MountManager
from nubix.core.rclone_engine import RcloneEngine
from nubix.core.remote_registry import RemoteRegistry
from nubix.core.scheduler import Scheduler
from nubix.core.sync_manager import SyncManager
from nubix.core.updater import Updater
from nubix.exceptions import RcloneNotFoundError

logger = logging.getLogger(__name__)

# bisync errors that Nubix recovers from on its own (automatic --resync on the
# next run). They describe the recovery mechanism, not a condition the user
# could act on — popping up "Sync Error" for them is pure noise.
_SELF_HEALING_ERRORS = (
    "cannot find prior Path1 or Path2 listings",
    "Must run --resync to recover",
    "too many deletes",
)


def is_self_healing_error(message: str) -> bool:
    """True if this sync error is fixed automatically by the next run."""
    return any(marker in message for marker in _SELF_HEALING_ERRORS)


def _setup_logging():
    # INFO by default — set NUBIX_DEBUG=1 for full debug output.
    level = logging.DEBUG if os.environ.get("NUBIX_DEBUG") else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    # Quieten noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    # watchdog logs every single inotify event at DEBUG — with large sync
    # trees that floods the console and burns CPU even under NUBIX_DEBUG.
    logging.getLogger("watchdog").setLevel(logging.WARNING)


class NubixApp:
    """Application controller. Owns and initialises all subsystems."""

    def __init__(self, qt_app: QApplication):
        _setup_logging()
        self._qt_app = qt_app
        self._window = None
        self._tray = None
        # Notification throttles: job_failed fires once per rclone error LINE,
        # and the auto-sync timer retries every 5 minutes — without these sets
        # an unplugged drive or a flaky remote floods the desktop with popups.
        self._drive_notified: set[str] = set()  # jobs already notified "drive missing"
        self._error_notified: set[str] = set()  # jobs already notified since last success
        self._run_active: set[str] = set()  # jobs with a running rclone process
        self._failed_runs: dict[str, int] = {}  # consecutive failed runs per job

        # --- Core subsystems (dependency order) ---
        self._config = ConfigManager()
        self._vault = CredentialVault()

        try:
            rclone_binary = self._config.get("general.rclone_binary", "")
            self._engine = RcloneEngine(binary_override=rclone_binary)
            logger.info("rclone: %s", self._engine.check_version())
        except RcloneNotFoundError as e:
            self._show_rclone_missing(str(e.user_message))
            self._engine = None

        self._registry = RemoteRegistry(self._config, self._vault)

        self._bandwidth = BandwidthController(self._config)

        if self._engine:
            self._sync_manager = SyncManager(self._engine, bandwidth=self._bandwidth)
            self._mount_manager = MountManager(self._engine)
        else:
            self._sync_manager = None
            self._mount_manager = None

        self._file_watcher = FileWatcher()
        if self._sync_manager:
            self._file_watcher.sync_needed.connect(self._on_watcher_sync_needed)
            # Suspend the watcher while a job's own bisync writes into the
            # watched directory — otherwise every sync immediately schedules
            # the next one (wasted rclone runs and remote API calls).
            self._sync_manager.job_started.connect(self._file_watcher.suspend_watch)
            self._sync_manager.job_finished.connect(
                lambda jid, code: self._file_watcher.resume_watch(jid)
            )

        self._scheduler = Scheduler()
        if self._sync_manager:
            self._scheduler.trigger_start.connect(self._on_scheduler_trigger_start)
            self._scheduler.trigger_stop.connect(self._sync_manager.stop_job)

        # Keep scheduler and file watcher in sync when remotes are updated/removed
        self._registry.remote_updated.connect(self._on_remote_updated)
        self._registry.remote_removed.connect(self._on_remote_removed)
        self._registry.remote_added.connect(self._on_remote_added)
        self._updater = Updater()

        qt_app.aboutToQuit.connect(self._shutdown)

    def start(self, background: bool = False):
        """Show the main window and start background services."""
        from nubix.ui.main_window import MainWindow
        from nubix.ui.system_tray import SystemTray
        from nubix.ui.theme import STYLESHEET

        self._qt_app.setStyleSheet(STYLESHEET)

        self._window = MainWindow(
            config=self._config,
            registry=self._registry,
            sync_manager=self._sync_manager or _NullSyncManager(),
            scheduler=self._scheduler,
            bandwidth=self._bandwidth,
            vault=self._vault,
            engine=self._engine or _NullEngine(),
            updater=self._updater,
            mount_manager=self._mount_manager,
        )

        # System tray
        if SystemTray.isSystemTrayAvailable():
            self._tray = SystemTray()
            self._tray.show_window_requested.connect(self._show_window)
            self._tray.sync_all_requested.connect(self._window._dashboard._sync_all)
            self._tray.pause_all_requested.connect(self._window._dashboard._pause_all)
            self._tray.settings_requested.connect(self._window.open_settings)
            self._tray.quit_requested.connect(self._qt_app.quit)
            self._tray.check_updates_requested.connect(self._updater.check_for_updates)
            if self._sync_manager:
                self._sync_manager.any_job_active.connect(self._tray.set_syncing)
                self._sync_manager.job_failed.connect(self._notify_job_failed)
                self._sync_manager.job_skipped.connect(self._notify_job_skipped)
                self._sync_manager.job_finished.connect(self._on_job_finished_notify)
                self._sync_manager.job_started.connect(self._on_job_started_notify)
            self._tray.show()

        # Connect updater
        self._updater.update_available.connect(self._on_update_available)

        if not background:
            self._window.show()
        self._scheduler.start()

        # Start file watcher and register all existing non-mount remotes
        self._file_watcher.start()
        for rc in self._registry.list_remotes():
            self._register_watcher(rc)

        # Auto-mount all enabled mount-mode remotes
        if self._mount_manager:
            from nubix.core.sync_job import SyncMode
            from pathlib import Path

            for rc in self._registry.list_remotes():
                if rc.is_enabled and rc.sync_mode == SyncMode.MOUNT:
                    self._mount_manager.mount(
                        rc.remote_id,
                        rc.remote_path,
                        Path(rc.local_path),
                        rc.mount_cache_mode,
                        rc.mount_cache_size,
                    )

        # Auto-sync timer — syncs all enabled non-mount remotes every 5 minutes
        # so that cloud deletions/changes are picked up without manual action.
        if self._sync_manager:
            from PySide6.QtCore import QTimer as _QTimer

            self._auto_sync_timer = _QTimer(self._window)
            self._auto_sync_timer.setInterval(5 * 60 * 1000)  # 5 minutes
            self._auto_sync_timer.timeout.connect(self._auto_sync_all)
            self._auto_sync_timer.start()
            logger.info("Auto-sync timer started (interval: 5 min)")

        # Check for updates after a short delay (don't block startup)
        from PySide6.QtCore import QTimer

        QTimer.singleShot(5000, self._updater.check_for_updates)

        # Auto-start scheduled jobs
        if self._sync_manager:
            for rc in self._registry.list_remotes():
                if rc.is_enabled and rc.is_scheduled:
                    self._scheduler.add_job(rc.to_sync_job())

        logger.info("Nubix started")

    def _show_window(self):
        if self._window:
            self._window.show()
            self._window.raise_()
            self._window.activateWindow()

    # ------------------------------------------------------------------
    # Tray notifications (throttled, honoring Settings → Notifications)
    # ------------------------------------------------------------------

    def _notifications_enabled(self) -> bool:
        return self._config.get("general.notifications", "errors_only") != "none"

    def _notify_job_failed(self, job_id: str, err: str) -> None:
        if is_self_healing_error(err):
            logger.info("Job %s: self-healing bisync condition, no notification: %s", job_id, err)
            return
        if job_id in self._error_notified:
            return
        # A mid-run rclone error is often a one-off (cloud API hiccup) that the
        # 5-minute retry heals on its own — only notify once a previous run
        # already failed. Failures to even start the job (job never ran) are
        # configuration problems and notify immediately.
        if job_id in self._run_active and self._failed_runs.get(job_id, 0) < 1:
            return
        self._error_notified.add(job_id)
        if self._tray and self._notifications_enabled():
            self._tray.notify("Sync Error", err, error=True)

    def _notify_job_skipped(self, job_id: str, reason: str) -> None:
        # One informational popup per unplugged-drive phase, not one per retry.
        if job_id in self._drive_notified:
            return
        self._drive_notified.add(job_id)
        if self._tray and self._notifications_enabled():
            self._tray.notify("Sync Paused", reason, error=False)

    def _on_job_started_notify(self, job_id: str) -> None:
        self._run_active.add(job_id)
        # The drive is back — notify again if it goes missing later.
        self._drive_notified.discard(job_id)

    def _on_job_finished_notify(self, job_id: str, exit_code: int) -> None:
        self._run_active.discard(job_id)
        if exit_code == 0:
            # Healed: the next failure phase notifies again — once.
            self._failed_runs.pop(job_id, None)
            self._error_notified.discard(job_id)
        else:
            self._failed_runs[job_id] = self._failed_runs.get(job_id, 0) + 1

    def _on_remote_added(self, rc) -> None:
        """Register watcher or start mount for a newly added remote."""
        from nubix.core.sync_job import SyncMode

        self._register_watcher(rc)
        if rc.is_enabled and rc.sync_mode == SyncMode.MOUNT and self._mount_manager:
            self._mount_manager.mount(
                rc.remote_id,
                rc.remote_path,
                Path(rc.local_path),
                rc.mount_cache_mode,
                rc.mount_cache_size,
            )

    def _on_remote_removed(self, remote_id: str):
        """Clean up all subsystems when a remote is deleted."""
        self._file_watcher.remove_watch(remote_id)
        if self._mount_manager:
            self._mount_manager.unmount(remote_id)
        if self._sync_manager:
            self._sync_manager.stop_job(remote_id)
        self._scheduler.remove_job(remote_id)
        if self._engine:
            self._engine.delete_remote(remote_id)

    def _on_remote_updated(self, rc):
        """Refresh scheduler and file watcher when a remote's settings change."""
        self._file_watcher.remove_watch(rc.remote_id)
        self._register_watcher(rc)
        # A stale status (e.g. "Drive missing" from an old local_path) must not
        # stick to the card after the settings changed — the next sync attempt
        # re-evaluates from scratch anyway.
        if self._sync_manager:
            self._sync_manager.reset_status(rc.remote_id)
        self._scheduler.remove_job(rc.remote_id)
        if rc.is_enabled and rc.is_scheduled:
            job = rc.to_sync_job()
            if job.schedule_windows:
                try:
                    self._scheduler.add_job(job)
                except Exception as e:
                    logger.warning("Scheduler update failed for %s: %s", rc.remote_id, e)

    def _register_watcher(self, rc) -> None:
        """Add a file system watch for *rc* if eligible (enabled, non-mount)."""
        from nubix.core.local_drive import missing_mount_for
        from nubix.core.sync_job import SyncMode

        if not rc.is_enabled:
            return
        if rc.sync_mode == SyncMode.MOUNT:
            return  # mount-mode writes directly through FUSE — no watcher needed
        if rc.remote_id in self._file_watcher.watched_ids():
            return  # already watching
        local = Path(rc.local_path)
        # Never mkdir on an unplugged external drive — that would create the
        # directory on the system partition and watch (and later sync) the
        # wrong disk. The auto-sync tick re-registers once the drive is back.
        if missing_mount_for(local) is not None:
            logger.info("Watcher for %s deferred — drive not mounted (%s)", rc.remote_id, local)
            return
        # Create the local directory if it doesn't exist yet so the watcher
        # can be registered immediately rather than being silently skipped.
        try:
            local.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        if local.exists():
            # add_watch may fail (e.g. inotify limit) — the periodic auto-sync
            # tick retries, so a later attempt can still succeed. Only claim
            # success when the watch was actually registered.
            if self._file_watcher.add_watch(rc.remote_id, local):
                logger.info("Auto-watcher registered for %s → %s", rc.remote_id, local)
        else:
            logger.warning(
                "Cannot register watcher for %s: path %s does not exist", rc.remote_id, local
            )

    @staticmethod
    def _sync_allowed_now(job) -> bool:
        """Scheduled jobs may only run inside their configured time windows."""
        from nubix.core.scheduler import is_in_window

        if not job.is_scheduled or not job.schedule_windows:
            return True
        return is_in_window(job.schedule_windows)

    def _auto_sync_all(self) -> None:
        """Triggered every 5 minutes — sync all enabled non-mount remotes."""
        if not self._sync_manager:
            return
        from nubix.core.sync_job import SyncMode

        for rc in self._registry.list_remotes():
            if not rc.is_enabled:
                continue
            if rc.sync_mode == SyncMode.MOUNT:
                # Retry mounts that were deferred because their drive was
                # unplugged. mount() re-checks the drive and defers again
                # silently if it is still missing.
                if self._mount_manager and self._mount_manager.is_waiting_for_drive(rc.remote_id):
                    self._mount_manager.mount(
                        rc.remote_id,
                        rc.remote_path,
                        Path(rc.local_path),
                        rc.mount_cache_mode,
                        rc.mount_cache_size,
                    )
                continue
            # Re-register the watcher for drives that were unplugged at
            # startup and have been mounted since (no-op when watching).
            self._register_watcher(rc)
            job = rc.to_sync_job()
            if not self._sync_allowed_now(job):
                logger.debug("Auto-sync: %s outside its schedule window", rc.remote_id)
                continue
            logger.debug("Auto-sync: starting job for %s", rc.remote_id)
            self._sync_manager.start_job(job)

    def _on_watcher_sync_needed(self, remote_id: str) -> None:
        """Triggered by file watcher debounce — start a sync if not already running."""
        if not self._sync_manager:
            return
        for rc in self._registry.list_remotes():
            if rc.remote_id == remote_id:
                job = rc.to_sync_job()
                if not self._sync_allowed_now(job):
                    logger.debug("Watcher sync for %s outside its schedule window", remote_id)
                    return
                logger.info("Auto-sync triggered by file change: %s", remote_id)
                self._sync_manager.start_job(job)
                return

    def _on_scheduler_trigger_start(self, job_id: str):
        if not self._sync_manager:
            return
        # Find the remote and start
        for rc in self._registry.list_remotes():
            if rc.remote_id == job_id:
                self._sync_manager.start_job(rc.to_sync_job())
                return

    def _on_update_available(self, release):
        from nubix.ui.update_dialog import UpdateDialog

        # The Settings → Updates tab handles this signal itself; popping a
        # modal on top of it would create two competing download paths.
        if self._window and self._window.is_settings_open():
            return
        # Never stack a second dialog (signal fires on every periodic check).
        if getattr(self, "_update_dialog", None) is not None:
            return
        self._update_dialog = UpdateDialog(release, self._updater, self._window)
        try:
            self._update_dialog.exec()
        finally:
            self._update_dialog = None

    def _shutdown(self):
        logger.info("Nubix shutting down…")
        self._scheduler.stop()
        if hasattr(self, "_auto_sync_timer"):
            self._auto_sync_timer.stop()
        self._file_watcher.stop()
        if self._mount_manager:
            self._mount_manager.unmount_all()
        if self._sync_manager:
            self._sync_manager.stop_all()
        if self._window:
            self._window._save_geometry()
        logger.info("Shutdown complete")

    def _show_rclone_missing(self, message: str):
        QMessageBox.warning(
            None,
            "rclone Not Found",
            f"{message}\n\nYou can install it with:\n  sudo apt install rclone\n\nor download it from https://rclone.org/downloads/",
        )


# Null objects for graceful degradation when rclone is missing
class _NullSyncManager:
    """No-op sync manager when rclone is not available."""

    def __init__(self):
        self.any_job_active = _NullSignal()
        self.job_started = _NullSignal()
        self.job_finished = _NullSignal()
        self.job_failed = _NullSignal()
        self.job_skipped = _NullSignal()
        self.job_status_changed = _NullSignal()
        self.progress_updated = _NullSignal()
        self.file_transferred = _NullSignal()

    def start_job(self, job):
        pass

    def stop_job(self, job_id):
        pass

    def pause_job(self, job_id):
        pass

    def resume_job(self, job_id):
        pass

    def stop_all(self):
        pass

    def is_any_active(self):
        return False

    def active_job_ids(self):
        return []

    def get_status(self, job_id):
        from nubix.core.sync_job import JobStatus

        return JobStatus.IDLE


class _NullEngine:
    """No-op engine when rclone is not available."""

    def check_version(self):
        return "not installed"

    def list_remotes(self):
        return []

    def list_remote_dirs(self, *a, **kw):
        return []

    def configure_remote(self, *a, **kw):
        return False

    def delete_remote(self, *a, **kw):
        return False

    def start_sync(self, job):
        raise RcloneNotFoundError()


class _NullSignal:
    def connect(self, *a, **kw):
        pass

    def disconnect(self, *a, **kw):
        pass

    def emit(self, *a, **kw):
        pass
