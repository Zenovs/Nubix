"""Single remote sync status card for the dashboard."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Qt, QTimer, Signal
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
from nubix.core.sync_job import JobStatus, SyncMode, TransferStats
from nubix.ui.widgets.animated_spinner import AnimatedSpinner
from nubix.ui.widgets.status_badge import StatusBadge

# rclone VFS cache root
_VFS_CACHE_ROOT = Path.home() / ".cache" / "rclone" / "vfs"


def _provider_icon(provider_type: str) -> str:
    """Return the icon for a provider type by looking it up in the registry."""
    try:
        from nubix.providers import get_provider

        return get_provider(provider_type).icon
    except Exception:
        return "☁"


def _format_bytes(b: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


def _format_speed(bps: float) -> str:
    return _format_bytes(int(bps)) + "/s"


def _dir_size(path: Path) -> int:
    """Return total bytes of all files under *path*. Returns 0 if not found."""
    total = 0
    try:
        for f in path.rglob("*"):
            if f.is_file():
                try:
                    total += f.stat().st_size
                except OSError:
                    pass
    except Exception:
        pass
    return total


class _CacheSizeThread(QThread):
    """Calculates VFS cache size for one remote in the background."""

    result = Signal(int)  # bytes used

    def __init__(self, remote_id: str, parent=None):
        super().__init__(parent)
        self._remote_id = remote_id

    def run(self):
        # rclone stores the VFS cache under a directory that starts with
        # "<remote_id>" inside ~/.cache/rclone/vfs/.  Scan all subdirs that
        # start with the remote name and sum their sizes.
        total = 0
        try:
            if _VFS_CACHE_ROOT.exists():
                for entry in _VFS_CACHE_ROOT.iterdir():
                    if entry.is_dir() and entry.name.startswith(self._remote_id):
                        total += _dir_size(entry)
        except Exception:
            pass
        self.result.emit(total)


class SyncStatusCard(QFrame):
    """Dashboard card for one configured remote."""

    sync_requested = Signal(str)  # remote_id
    stop_requested = Signal(str)  # remote_id
    mount_requested = Signal(str)  # remote_id
    unmount_requested = Signal(str)  # remote_id
    settings_requested = Signal(str)  # remote_id

    def __init__(self, remote: RemoteConfig, parent=None):
        super().__init__(parent)
        self.remote = remote
        self._current_status = JobStatus.IDLE
        self._cache_thread: _CacheSizeThread | None = None
        self._cache_timer = QTimer(self)
        self._cache_timer.setInterval(10_000)  # refresh every 10 s
        self._cache_timer.timeout.connect(self._refresh_cache_size)
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

        provider_icon = _provider_icon(self.remote.provider_type)
        self._name_label = QLabel(f"{provider_icon}  {self.remote.display_name}")
        self._name_label.setStyleSheet(
            "color: #E2E2F0; font-size: 14px; font-weight: 700; background: transparent;"
        )
        name_col.addWidget(self._name_label)

        self._path_label = QLabel(self.remote.local_path)
        self._path_label.setStyleSheet("color: #8888AA; font-size: 11px; background: transparent;")
        self._path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        name_col.addWidget(self._path_label)
        top.addLayout(name_col, 1)

        self._badge = StatusBadge(JobStatus.IDLE)
        top.addWidget(self._badge)

        is_mount = self.remote.sync_mode == SyncMode.MOUNT
        primary_label = "⏏  Mount" if is_mount else "▶  Sync"
        self._btn_sync = QPushButton(primary_label)
        self._btn_sync.setFixedWidth(90)
        self._btn_sync.setStyleSheet(
            "QPushButton { background: #7C5CFC; color: white; border: none;"
            " border-radius: 7px; padding: 6px 12px; font-weight: 600; font-size: 12px; }"
            "QPushButton:hover { background: #9070FF; }"
            "QPushButton:pressed { background: #6040E0; }"
            "QPushButton:disabled { background: #2E2E50; color: #4A4A6A; }"
        )
        if is_mount:
            self._btn_sync.clicked.connect(lambda: self.mount_requested.emit(self.remote.remote_id))
        else:
            self._btn_sync.clicked.connect(lambda: self.sync_requested.emit(self.remote.remote_id))
        top.addWidget(self._btn_sync)

        stop_label = "⏏" if is_mount else "⏹"
        stop_tip = "Unmount" if is_mount else "Stop sync"
        self._btn_stop = QPushButton(stop_label)
        self._btn_stop.setFixedSize(34, 34)
        self._btn_stop.setEnabled(False)
        self._btn_stop.setStyleSheet(
            "QPushButton { background: #2A0A0A; color: #F87171; border: 1px solid #F8717140;"
            " border-radius: 7px; font-size: 14px; }"
            "QPushButton:hover { background: #F87171; color: white; }"
            "QPushButton:disabled { background: #1E1E32; color: #4A4A6A; border-color: #2E2E50; }"
        )
        self._btn_stop.setToolTip(stop_tip)
        if is_mount:
            self._btn_stop.clicked.connect(
                lambda: self.unmount_requested.emit(self.remote.remote_id)
            )
        else:
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

        # ── Bottom row: current file / cache info + speed ──
        bottom = QHBoxLayout()
        bottom.setSpacing(8)

        self._file_label = QLabel("")
        self._file_label.setStyleSheet("color: #8888AA; font-size: 11px; background: transparent;")
        self._file_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        bottom.addWidget(self._file_label, 1)

        # Cache row — only relevant for mount mode
        self._cache_bar = QProgressBar()
        self._cache_bar.setRange(0, 100)
        self._cache_bar.setValue(0)
        self._cache_bar.setTextVisible(False)
        self._cache_bar.setFixedSize(60, 6)
        self._cache_bar.setStyleSheet(
            "QProgressBar { border: none; border-radius: 3px; background: #2E2E50; }"
            "QProgressBar::chunk { border-radius: 3px; background: #A78BFA; }"
        )
        self._cache_bar.setToolTip("Local cache usage")
        self._cache_bar.setVisible(is_mount)
        bottom.addWidget(self._cache_bar)

        self._cache_label = QLabel("")
        self._cache_label.setStyleSheet(
            "color: #A78BFA; font-size: 11px; font-weight: 600; background: transparent;"
        )
        self._cache_label.setToolTip("Files cached locally / max cache size")
        self._cache_label.setVisible(is_mount)
        bottom.addWidget(self._cache_label)

        self._speed_label = QLabel("")
        self._speed_label.setStyleSheet(
            "color: #7C5CFC; font-size: 11px; font-weight: 600; background: transparent;"
        )
        bottom.addWidget(self._speed_label)

        root.addLayout(bottom)

    # ------------------------------------------------------------------
    # Status updates
    # ------------------------------------------------------------------

    def update_status(self, status: JobStatus) -> None:
        self._current_status = status
        self._badge.set_status(status)
        is_syncing = status == JobStatus.SYNCING
        is_mounted = status == JobStatus.MOUNTED
        busy = is_syncing or is_mounted
        self._btn_sync.setEnabled(not busy)
        self._btn_stop.setEnabled(busy)
        if is_syncing:
            self._spinner.start()
        else:
            self._spinner.stop()
        if status == JobStatus.UP_TO_DATE:
            self._progress.setValue(100)
        if status in (JobStatus.IDLE, JobStatus.MOUNTED):
            self._progress.setValue(0)
            self._file_label.setText("")
            self._speed_label.setText("")

        # Start or stop cache size polling
        if is_mounted:
            self._refresh_cache_size()
            self._cache_timer.start()
        else:
            self._cache_timer.stop()
            if self.remote.sync_mode == SyncMode.MOUNT:
                self._cache_label.setText("not mounted")
                self._cache_bar.setValue(0)

    def update_progress(self, stats: TransferStats) -> None:
        pct = int(stats.percent)
        self._progress.setValue(max(0, min(100, pct)))
        if stats.current_file:
            fname = Path(stats.current_file).name
            self._file_label.setText(fname)
        if stats.speed_bps > 0:
            self._speed_label.setText(_format_speed(stats.speed_bps))

    # ------------------------------------------------------------------
    # Cache size polling
    # ------------------------------------------------------------------

    def _refresh_cache_size(self) -> None:
        """Kick off a background thread to measure VFS cache size."""
        if self._cache_thread and self._cache_thread.isRunning():
            return
        self._cache_thread = _CacheSizeThread(self.remote.remote_id, self)
        self._cache_thread.result.connect(self._on_cache_size)
        self._cache_thread.start()

    def _on_cache_size(self, used_bytes: int) -> None:
        """Update cache label and bar from background result."""
        # Parse max size from RemoteConfig (e.g. "1G", "500M")
        max_bytes = _parse_size(self.remote.mount_cache_size)
        used_str = _format_bytes(used_bytes)
        max_str = _format_bytes(max_bytes)
        self._cache_label.setText(f"Cache: {used_str} / {max_str}")
        if max_bytes > 0:
            pct = min(100, int(used_bytes / max_bytes * 100))
            self._cache_bar.setValue(pct)
            # Turn bar red when > 80% full
            if pct >= 80:
                self._cache_bar.setStyleSheet(
                    "QProgressBar { border: none; border-radius: 3px; background: #2E2E50; }"
                    "QProgressBar::chunk { border-radius: 3px; background: #F87171; }"
                )
            else:
                self._cache_bar.setStyleSheet(
                    "QProgressBar { border: none; border-radius: 3px; background: #2E2E50; }"
                    "QProgressBar::chunk { border-radius: 3px; background: #A78BFA; }"
                )


def _parse_size(s: str) -> int:
    """Parse rclone size string like '1G', '500M', '2T' into bytes."""
    s = s.strip().upper()
    units = {"B": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
    for suffix, mult in units.items():
        if s.endswith(suffix):
            try:
                return int(float(s[:-1]) * mult)
            except ValueError:
                return 0
    try:
        return int(s)
    except ValueError:
        return 0
