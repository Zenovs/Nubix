"""System tray icon for Nubix."""

from __future__ import annotations

from PySide6.QtGui import QIcon, QPixmap, QColor
from PySide6.QtWidgets import QMenu, QSystemTrayIcon
from PySide6.QtCore import Signal


def _make_colored_icon(color: str, size: int = 22) -> QIcon:
    """Generate a simple colored circle icon (fallback when no icon file)."""
    pix = QPixmap(size, size)
    pix.fill(QColor(0, 0, 0, 0))
    from PySide6.QtGui import QPainter, QBrush
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QBrush(QColor(color)))
    painter.setPen(QColor(color).darker(120))
    painter.drawEllipse(2, 2, size - 4, size - 4)
    painter.end()
    return QIcon(pix)


_ICON_IDLE = _make_colored_icon("#4A90D9")
_ICON_SYNCING = _make_colored_icon("#43A047")
_ICON_ERROR = _make_colored_icon("#E53935")


class SystemTray(QSystemTrayIcon):
    """System tray icon with context menu."""

    show_window_requested = Signal()
    sync_all_requested = Signal()
    pause_all_requested = Signal()
    settings_requested = Signal()
    check_updates_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(_ICON_IDLE, parent)
        self.setToolTip("Nubix — Cloud Sync")
        self._build_menu()
        self.activated.connect(self._on_activated)

    def _build_menu(self):
        menu = QMenu()
        act_show = menu.addAction("Show Nubix")
        act_show.triggered.connect(self.show_window_requested)
        menu.addSeparator()

        act_sync = menu.addAction("↻  Sync All Now")
        act_sync.triggered.connect(self.sync_all_requested)

        act_pause = menu.addAction("⏸  Pause All")
        act_pause.triggered.connect(self.pause_all_requested)

        menu.addSeparator()
        act_settings = menu.addAction("⚙  Settings")
        act_settings.triggered.connect(self.settings_requested)

        menu.addSeparator()
        act_update = menu.addAction("Check for Updates")
        act_update.triggered.connect(self.check_updates_requested)

        menu.addSeparator()
        act_quit = menu.addAction("Quit Nubix")
        act_quit.triggered.connect(self.quit_requested)

        self.setContextMenu(menu)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_window_requested.emit()

    def set_syncing(self, active: bool):
        self.setIcon(_ICON_SYNCING if active else _ICON_IDLE)
        self.setToolTip("Nubix — Syncing…" if active else "Nubix — Up to date")

    def set_error(self):
        self.setIcon(_ICON_ERROR)
        self.setToolTip("Nubix — Error (click to view)")

    def notify(self, title: str, message: str, error: bool = False):
        icon = (
            QSystemTrayIcon.MessageIcon.Critical
            if error
            else QSystemTrayIcon.MessageIcon.Information
        )
        self.showMessage(title, message, icon, 4000)
