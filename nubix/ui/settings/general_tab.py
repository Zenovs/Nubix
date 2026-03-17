"""General settings tab."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from nubix.constants import AUTOSTART_FILE
from nubix.core.config_manager import ConfigManager


class GeneralTab(QWidget):
    def __init__(self, config: ConfigManager, parent=None):
        super().__init__(parent)
        self._config = config
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._autostart = QCheckBox("Start Nubix when I log in")
        form.addRow("Autostart:", self._autostart)

        self._minimize_to_tray = QCheckBox("Minimize to system tray when closed")
        form.addRow("Window close:", self._minimize_to_tray)

        self._notifications = QComboBox()
        self._notifications.addItems(["All events", "Errors only", "None"])
        form.addRow("Notifications:", self._notifications)

        rclone_row = QHBoxLayout()
        self._rclone_path = QLineEdit()
        self._rclone_path.setPlaceholderText("Auto-detect (recommended)")
        rclone_row.addWidget(self._rclone_path, 1)
        btn_browse = QPushButton("Browse…")
        btn_browse.setFixedWidth(80)
        btn_browse.clicked.connect(self._browse_rclone)
        rclone_row.addWidget(btn_browse)
        rclone_container = QWidget()
        rclone_container.setLayout(rclone_row)
        form.addRow("rclone binary:", rclone_container)

        self._log_retention = QSpinBox()
        self._log_retention.setRange(1, 365)
        self._log_retention.setSuffix(" days")
        form.addRow("Log retention:", self._log_retention)

        layout.addLayout(form)
        layout.addStretch()

    def _load(self):
        self._autostart.setChecked(self._config.get("general.autostart", False))
        self._minimize_to_tray.setChecked(self._config.get("general.minimize_to_tray", True))
        notif_map = {"all": 0, "errors_only": 1, "none": 2}
        notif = self._config.get("general.notifications", "errors_only")
        self._notifications.setCurrentIndex(notif_map.get(notif, 1))
        self._rclone_path.setText(self._config.get("general.rclone_binary", ""))
        self._log_retention.setValue(self._config.get("general.log_retention_days", 30))

    def save(self):
        self._config.set("general.autostart", self._autostart.isChecked())
        self._config.set("general.minimize_to_tray", self._minimize_to_tray.isChecked())
        notif_values = ["all", "errors_only", "none"]
        self._config.set("general.notifications", notif_values[self._notifications.currentIndex()])
        self._config.set("general.rclone_binary", self._rclone_path.text().strip())
        self._config.set("general.log_retention_days", self._log_retention.value())

        # Handle autostart .desktop file
        self._update_autostart(self._autostart.isChecked())

    def _browse_rclone(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select rclone binary", "/usr/bin")
        if path:
            self._rclone_path.setText(path)

    def _update_autostart(self, enable: bool):
        import shutil

        AUTOSTART_FILE.parent.mkdir(parents=True, exist_ok=True)
        if enable:
            binary = shutil.which("nubix") or "nubix"
            content = (
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=Nubix\n"
                f"Exec={binary} --background\n"
                "Hidden=false\n"
                "NoDisplay=false\n"
                "X-GNOME-Autostart-enabled=true\n"
            )
            AUTOSTART_FILE.write_text(content)
        else:
            if AUTOSTART_FILE.exists():
                AUTOSTART_FILE.unlink()
