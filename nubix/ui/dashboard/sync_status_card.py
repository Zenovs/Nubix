"""Single remote sync status card for the dashboard."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from nubix.core.remote_registry import RemoteConfig
from nubix.core.sync_job import JobStatus, TransferStats
from nubix.ui.widgets.animated_spinner import AnimatedSpinner
from nubix.ui.widgets.status_badge import StatusBadge


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
        self.setMinimumHeight(110)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(6)

        # --- Top row: icon + name + status badge + buttons ---
        top = QHBoxLayout()
        top.setSpacing(10)

        self._spinner = AnimatedSpinner(20, parent=self)
        top.addWidget(self._spinner)

        name_col = QVBoxLayout()
        name_col.setSpacing(2)
        self._name_label = QLabel(f"<b>{self.remote.display_name}</b>")
        self._path_label = QLabel(self.remote.local_path)
        self._path_label.setStyleSheet("color: #666; font-size: 11px;")
        self._path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        name_col.addWidget(self._name_label)
        name_col.addWidget(self._path_label)
        top.addLayout(name_col, 1)

        self._badge = StatusBadge(JobStatus.IDLE)
        top.addWidget(self._badge)

        self._btn_sync = QPushButton("Sync Now")
        self._btn_sync.setFixedWidth(90)
        self._btn_sync.clicked.connect(lambda: self.sync_requested.emit(self.remote.remote_id))
        top.addWidget(self._btn_sync)

        self._btn_stop = QPushButton("Stop")
        self._btn_stop.setFixedWidth(60)
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(lambda: self.stop_requested.emit(self.remote.remote_id))
        top.addWidget(self._btn_stop)

        self._btn_settings = QPushButton("⚙")
        self._btn_settings.setFixedSize(28, 28)
        self._btn_settings.setFlat(True)
        self._btn_settings.setToolTip("Settings")
        self._btn_settings.clicked.connect(
            lambda: self.settings_requested.emit(self.remote.remote_id)
        )
        top.addWidget(self._btn_settings)

        root.addLayout(top)

        # --- Progress bar ---
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(True)
        self._progress.setFixedHeight(8)
        self._progress.setStyleSheet(
            "QProgressBar { border: none; border-radius: 4px; background: #e0e0e0; }"
            "QProgressBar::chunk { border-radius: 4px; background: #4A90D9; }"
        )
        root.addWidget(self._progress)

        # --- Bottom row: current file + speed ---
        bottom = QHBoxLayout()
        self._file_label = QLabel("")
        self._file_label.setStyleSheet("color: #555; font-size: 11px;")
        self._file_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._speed_label = QLabel("")
        self._speed_label.setStyleSheet("color: #555; font-size: 11px;")
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
            # Truncate long paths
            fname = Path(stats.current_file).name
            self._file_label.setText(fname)
        if stats.speed_bps > 0:
            self._speed_label.setText(_format_speed(stats.speed_bps))
