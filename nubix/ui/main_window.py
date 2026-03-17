"""Main application window."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStackedWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
)

from nubix.constants import WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT, SIDEBAR_WIDTH
from nubix.core.bandwidth_controller import BandwidthController
from nubix.core.config_manager import ConfigManager
from nubix.core.credential_vault import CredentialVault
from nubix.core.rclone_engine import RcloneEngine
from nubix.core.remote_registry import RemoteRegistry
from nubix.core.scheduler import Scheduler
from nubix.core.sync_manager import SyncManager
from nubix.ui.dashboard.dashboard_widget import DashboardWidget
from nubix.ui.logs.log_viewer import LogViewer

logger = logging.getLogger(__name__)

_NAV_ITEMS = [
    ("Dashboard", "☁"),
    ("Log", "📋"),
    ("Settings", "⚙"),
]


class MainWindow(QMainWindow):
    """Main Nubix window with sidebar navigation."""

    def __init__(
        self,
        config: ConfigManager,
        registry: RemoteRegistry,
        sync_manager: SyncManager,
        scheduler: Scheduler,
        bandwidth: BandwidthController,
        vault: CredentialVault,
        engine: RcloneEngine,
        parent=None,
    ):
        super().__init__(parent)
        self._config = config
        self._registry = registry
        self._sync = sync_manager
        self._scheduler = scheduler
        self._bandwidth = bandwidth
        self._vault = vault
        self._engine = engine

        self.setWindowTitle("Nubix — Cloud Sync")
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        self._build_ui()
        self._connect_signals()
        self._restore_geometry()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sidebar
        sidebar = self._build_sidebar()
        root.addWidget(sidebar)

        # Separator line
        sep = QWidget()
        sep.setFixedWidth(1)
        sep.setStyleSheet("background: #ddd;")
        root.addWidget(sep)

        # Page stack
        self._stack = QStackedWidget()

        self._dashboard = DashboardWidget(self._registry, self._sync)
        self._stack.addWidget(self._dashboard)

        self._log_viewer = LogViewer()
        self._stack.addWidget(self._log_viewer)

        # Settings page — lazy loaded
        self._settings_placeholder = QLabel("Settings")
        self._settings_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._stack.addWidget(self._settings_placeholder)

        root.addWidget(self._stack, 1)

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(SIDEBAR_WIDTH)
        sidebar.setStyleSheet("background: #F5F5F5;")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # App header
        header = QWidget()
        header.setFixedHeight(56)
        header.setStyleSheet("background: #4A90D9;")
        hl = QHBoxLayout(header)
        title = QLabel("Nubix")
        title.setStyleSheet("color: white; font-size: 18px; font-weight: bold;")
        hl.addWidget(title)
        layout.addWidget(header)

        # Nav list
        self._nav = QListWidget()
        self._nav.setStyleSheet(
            "QListWidget { border: none; background: transparent; outline: none; }"
            "QListWidget::item { padding: 12px 16px; font-size: 14px; }"
            "QListWidget::item:selected { background: #E3F2FD; color: #1976D2; }"
            "QListWidget::item:hover { background: #EEEEEE; }"
        )
        for name, icon in _NAV_ITEMS:
            item = QListWidgetItem(f"{icon}  {name}")
            self._nav.addItem(item)
        self._nav.setCurrentRow(0)
        self._nav.currentRowChanged.connect(self._stack.setCurrentIndex)
        layout.addWidget(self._nav, 1)

        # Add connection button at bottom of sidebar
        btn_add = QPushButton("+ Add Connection")
        btn_add.setStyleSheet(
            "QPushButton { background: #4A90D9; color: white; border: none; "
            "padding: 12px; font-size: 13px; font-weight: bold; }"
            "QPushButton:hover { background: #1976D2; }"
        )
        btn_add.clicked.connect(self.open_wizard)
        layout.addWidget(btn_add)

        return sidebar

    def _connect_signals(self):
        self._sync.any_job_active.connect(self._on_any_active)
        self._sync.job_failed.connect(self._on_job_failed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def open_wizard(self):
        from nubix.ui.wizard.setup_wizard import SetupWizard

        wizard = SetupWizard(self._registry, self._vault, self._engine, self)
        wizard.exec()

    def open_settings(self):
        from nubix.ui.settings.settings_dialog import SettingsDialog

        dlg = SettingsDialog(self._config, self._registry, self._scheduler, self._bandwidth, self)
        dlg.exec()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_any_active(self, active: bool):
        title = "Nubix — Syncing…" if active else "Nubix — Cloud Sync"
        self.setWindowTitle(title)

    def _on_job_failed(self, job_id: str, error: str):
        logger.error("Job %s failed: %s", job_id, error)

    # ------------------------------------------------------------------
    # Window lifecycle
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        if self._config.get("general.minimize_to_tray", True):
            event.ignore()
            self.hide()
        else:
            if self._sync.is_any_active():
                reply = QMessageBox.question(
                    self,
                    "Sync in progress",
                    "A sync is running. Quit anyway?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    event.ignore()
                    return
            self._sync.stop_all()
            event.accept()

    def _restore_geometry(self):
        geom = self._config.get("ui.window_geometry")
        if geom:
            try:
                self.restoreGeometry(bytes.fromhex(geom))
            except Exception:
                pass

    def _save_geometry(self):
        self._config.set("ui.window_geometry", self.saveGeometry().toHex().data().decode())
