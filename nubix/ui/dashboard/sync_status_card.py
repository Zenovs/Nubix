"""Single remote sync status card for the dashboard."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from nubix.core.remote_registry import RemoteConfig
from nubix.core.sync_job import JobStatus, TransferStats
from nubix.ui.widgets.animated_spinner import AnimatedSpinner
from nubix.ui.widgets.status_badge import StatusBadge

_PROVIDER_ICONS = {
    "gdrive": "🟡",
    "dropbox": "🔵",
    "nextcloud": "☁",
}


def _format_bytes(b: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


def _format_speed(bps: float) -> str:
    return _format_bytes(int(bps)) + "/s"


class SyncStatusCard(QFrame):
    """Dashboard card for one configured remote."""

    sync_requested = Signal(str)  # remote_id
    stop_requested = Signal(str)  # remote_id
    settings_requested = Signal(str)  # remote_id

    def __init__(self, remote: RemoteConfig, parent=None):
        super().__init__(parent)
        self.remote = remote
        self._current_status = JobStatus.IDLE
        self.setObjectName("SyncStatusCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumHeight(120)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 14)
        root.setSpacing(10)

        # ── Top row: spinner + name/path + badge + buttons ──
        top = QHBoxLayout()
        top.setSpacing(12)

        self._spinner = AnimatedSpinner(22, color="#7C5CFC", parent=self)
        top.addWidget(self._spinner)

        # Provider icon + name column
        name_col = QVBoxLayout()
        name_col.setSpacing(3)

        provider_icon = _PROVIDER_ICONS.get(self.remote.provider_type, "☁")
        self._name_label = QLabel(f"{provider_icon}  {self.remote.display_name}")
        self._name_label.setStyleSheet(
            "color: #E2E2F0; font-size: 14px; font-weight: 700; background: transparent;"
        )
        name_col.addWidget(self._name_label)

        self._path_label = QLabel(self.remote.local_path)
        self._path_label.setStyleSheet(
            "color: #8888AA; font-size: 11px; background: transparent;"
        )
        self._path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        name_col.addWidget(self._path_label)
        top.addLayout(name_col, 1)

        self._badge = StatusBadge(JobStatus.IDLE)
        top.addWidget(self._badge)

        self._btn_sync = QPushButton("▶  Sync")
        self._btn_sync.setFixedWidth(84)
        self._btn_sync.setStyleSheet(
            "QPushButton { background: #7C5CFC; color: white; border: none;"
            " border-radius: 7px; padding: 6px 12px; font-weight: 600; font-size: 12px; }"
            "QPushButton:hover { background: #9070FF; }"
            "QPushButton:pressed { background: #6040E0; }"
            "QPushButton:disabled { background: #2E2E50; color: #4A4A6A; }"
        )
        self._btn_sync.clicked.connect(lambda: self.sync_requested.emit(self.remote.remote_id))
        top.addWidget(self._btn_sync)

        self._btn_stop = QPushButton("⏹")
        self._btn_stop.setFixedSize(34, 34)
        self._btn_stop.setEnabled(False)
        self._btn_stop.setStyleSheet(
            "QPushButton { background: #2A0A0A; color: #F87171; border: 1px solid #F8717140;"
            " border-radius: 7px; font-size: 14px; }"
            "QPushButton:hover { background: #F87171; color: white; }"
            "QPushButton:disabled { background: #1E1E32; color: #4A4A6A; border-color: #2E2E50; }"
        )
        self._btn_stop.setToolTip("Stop sync")
        self._btn_stop.clicked.connect(lambda: self.stop_requested.emit(self.remote.remote_id))
        top.addWidget(self._btn_stop)

        self._btn_settings = QPushButton("⚙")
        self._btn_settings.setFixedSize(34, 34)
        self._btn_settings.setFlat(True)
        self._btn_settings.setStyleSheet(
            "QPushButton { background: transparent; color: #8888AA; border: none;"
            " border-radius: 7px; font-size: 15px; }"
            "QPushButton:hover { background: #2E2E50; color: #E2E2F0; }"
        )
        self._btn_settings.setToolTip("Settings")
        self._btn_settings.clicked.connect(
            lambda: self.settings_requested.emit(self.remote.remote_id)
        )
        top.addWidget(self._btn_settings)

        root.addLayout(top)

        # ── Progress bar ──
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(6)
        self._progress.setStyleSheet(
            "QProgressBar { border: none; border-radius: 3px; background: #2E2E50; }"
            "QProgressBar::chunk { border-radius: 3px;"
            " background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            " stop:0 #7C5CFC, stop:1 #A78BFA); }"
        )
        root.addWidget(self._progress)

        # ── Bottom row: current file + speed ──
        bottom = QHBoxLayout()
        self._file_label = QLabel("")
        self._file_label.setStyleSheet(
            "color: #8888AA; font-size: 11px; background: transparent;"
        )
        self._file_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._speed_label = QLabel("")
        self._speed_label.setStyleSheet(
            "color: #7C5CFC; font-size: 11px; font-weight: 600; background: transparent;"
        )
        bottom.addWidget(self._file_label, 1)
        bottom.addWidget(self._speed_label)
        root.addLayout(bottom)

    def update_status(self, status: JobStatus) -> None:
        self._current_status = status
        self._badge.set_status(status)
        is_syncing = status == JobStatus.SYNCING
        self._btn_sync.setEnabled(not is_syncing)
        self._btn_stop.setEnabled(is_syncing)
        if is_syncing:
            self._spinner.start()
        else:
            self._spinner.stop()
        if status == JobStatus.UP_TO_DATE:
            self._progress.setValue(100)
        if status == JobStatus.IDLE:
            self._progress.setValue(0)
            self._file_label.setText("")
            self._speed_label.setText("")

    def update_progress(self, stats: TransferStats) -> None:
        pct = int(stats.percent)
        self._progress.setValue(max(0, min(100, pct)))
        if stats.current_file:
            fname = Path(stats.current_file).name
            self._file_label.setText(fname)
        if stats.speed_bps > 0:
            self._speed_label.setText(_format_speed(stats.speed_bps))
