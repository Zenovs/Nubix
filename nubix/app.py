"""
NubixApp — wires all subsystems together and manages application lifecycle.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from nubix.core.bandwidth_controller import BandwidthController
from nubix.core.config_manager import ConfigManager
from nubix.core.credential_vault import CredentialVault
from nubix.core.rclone_engine import RcloneEngine
from nubix.core.remote_registry import RemoteRegistry
from nubix.core.scheduler import Scheduler
from nubix.core.sync_manager import SyncManager
from nubix.core.updater import Updater
from nubix.exceptions import RcloneNotFoundError

logger = logging.getLogger(__name__)


def _setup_logging():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    # Quieten noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)


class NubixApp:
    """Application controller. Owns and initialises all subsystems."""

    def __init__(self, qt_app: QApplication):
        _setup_logging()
        self._qt_app = qt_app
        self._window = None
        self._tray = None

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

        if self._engine:
            self._sync_manager = SyncManager(self._engine)
        else:
            self._sync_manager = None

        self._scheduler = Scheduler()
        if self._sync_manager:
            self._scheduler.trigger_start.connect(self._on_scheduler_trigger_start)
            self._scheduler.trigger_stop.connect(self._sync_manager.stop_job)

        self._bandwidth = BandwidthController(self._config)
        self._updater = Updater()

        qt_app.aboutToQuit.connect(self._shutdown)

    def start(self):
        """Show the main window and start background services."""
        from nubix.ui.main_window import MainWindow
        from nubix.ui.system_tray import SystemTray

        self._window = MainWindow(
            config=self._config,
            registry=self._registry,
            sync_manager=self._sync_manager or _NullSyncManager(),
            scheduler=self._scheduler,
            bandwidth=self._bandwidth,
            vault=self._vault,
            engine=self._engine or _NullEngine(),
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
                self._sync_manager.job_failed.connect(
                    lambda jid, err: self._tray.notify("Sync Error", err, error=True)
                )
            self._tray.show()

        # Connect updater
        self._updater.update_available.connect(self._on_update_available)

        self._window.show()
        self._scheduler.start()

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
        dlg = UpdateDialog(release, self._updater, self._window)
        dlg.exec()

    def _shutdown(self):
        logger.info("Nubix shutting down…")
        self._scheduler.stop()
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

    any_job_active = property(lambda self: _NullSignal())
    job_failed = property(lambda self: _NullSignal())
    job_status_changed = property(lambda self: _NullSignal())
    progress_updated = property(lambda self: _NullSignal())
    file_transferred = property(lambda self: _NullSignal())

    def start_job(self, job): pass
    def stop_job(self, job_id): pass
    def pause_job(self, job_id): pass
    def resume_job(self, job_id): pass
    def stop_all(self): pass
    def is_any_active(self): return False
    def active_job_ids(self): return []
    def get_status(self, job_id): from nubix.core.sync_job import JobStatus; return JobStatus.IDLE


class _NullEngine:
    """No-op engine when rclone is not available."""

    def check_version(self): return "not installed"
    def list_remotes(self): return []
    def list_remote_dirs(self, *a, **kw): return []
    def configure_remote(self, *a, **kw): return False
    def delete_remote(self, *a, **kw): return False
    def start_sync(self, job): raise RcloneNotFoundError()
    def set_bandwidth_limit(self, limit): return False


class _NullSignal:
    def connect(self, *a, **kw): pass
    def disconnect(self, *a, **kw): pass
    def emit(self, *a, **kw): pass
