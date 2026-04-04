"""Main dashboard widget showing all cloud connections."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from nubix.core.mount_manager import MountManager
from nubix.core.remote_registry import RemoteConfig, RemoteRegistry
from nubix.core.sync_job import JobStatus, SyncMode, TransferStats
from nubix.core.sync_manager import SyncManager
from nubix.ui.dashboard.progress_panel import ProgressPanel
from nubix.ui.dashboard.sync_status_card import SyncStatusCard
from nubix.ui.dashboard.transfer_rate_widget import TransferRateWidget


class DashboardWidget(QWidget):
    """Top-level dashboard containing all remote cards."""

    remote_settings_requested = Signal(str)  # remote_id

    def __init__(
        self,
        registry: RemoteRegistry,
        sync_manager: SyncManager,
        mount_manager: MountManager | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._registry = registry
        self._sync = sync_manager
        self._mount = mount_manager
        self._cards: dict[str, SyncStatusCard] = {}
        self._jobs: dict[str, object] = {}  # remote_id -> SyncJob

        self._build_ui()
        self._connect_signals()
        self._load_existing_remotes()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # ── Header ──
        header = QHBoxLayout()
        title = QLabel("Cloud Connections")
        title.setStyleSheet(
            "color: #E2E2F0; font-size: 20px; font-weight: 700; background: transparent;"
        )
        header.addWidget(title)
        header.addStretch()

        self._btn_sync_all = QPushButton("↻   Sync All")
        self._btn_sync_all.setFixedWidth(120)
        self._btn_sync_all.setStyleSheet(
            "QPushButton { background: #7C5CFC; color: white; border: none;"
            " border-radius: 8px; padding: 8px 16px; font-weight: 600; }"
            "QPushButton:hover { background: #9070FF; }"
        )
        self._btn_sync_all.clicked.connect(self._sync_all)
        header.addWidget(self._btn_sync_all)

        self._btn_pause_all = QPushButton("⏸   Pause All")
        self._btn_pause_all.setFixedWidth(120)
        self._btn_pause_all.setStyleSheet(
            "QPushButton { background: #2E2E50; color: #E2E2F0; border: 1px solid #3E3E60;"
            " border-radius: 8px; padding: 8px 16px; font-weight: 600; }"
            "QPushButton:hover { background: #3E3E60; }"
            "QPushButton:disabled { background: #1E1E32; color: #4A4A6A; border-color: #2E2E50; }"
        )
        self._btn_pause_all.clicked.connect(self._pause_all)
        header.addWidget(self._btn_pause_all)

        root.addLayout(header)

        # ── Main splitter: cards | right panel ──
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        # Cards area
        cards_container = QWidget()
        self._cards_layout = QVBoxLayout(cards_container)
        self._cards_layout.setContentsMargins(0, 0, 8, 0)
        self._cards_layout.setSpacing(12)

        # Empty state — shown only when no connections exist
        self._empty_label = QLabel(
            "<p style='color:#6B6B8A; font-size:13px; margin:0;'>"
            "No connections yet — click  <b>＋ Add Connection</b>  to get started.</p>"
        )
        self._empty_label.setTextFormat(Qt.TextFormat.RichText)
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("background: transparent;")
        self._cards_layout.addWidget(self._empty_label)
        self._cards_layout.addStretch()

        # ASCII logo — always visible at the bottom
        _ASCII_HTML = (
            "<pre style='"
            "font-family: monospace; font-size: 11px; font-weight: bold;"
            " color: #2E2E4A; line-height: 1.2; letter-spacing: 0;"
            " margin: 0; padding: 0;'"
            ">"
            "███╗   ██╗██╗   ██╗██████╗ ██╗██╗  ██╗\n"
            "████╗  ██║██║   ██║██╔══██╗██║╚██╗██╔╝\n"
            "██╔██╗ ██║██║   ██║██████╔╝██║ ╚███╔╝ \n"
            "██║╚██╗██║██║   ██║██╔══██╗██║ ██╔██╗ \n"
            "██║ ╚████║╚██████╔╝██████╔╝██║██╔╝ ██╗\n"
            "╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ╚═╝╚═╝  ╚═╝"
            "</pre>"
        )
        self._ascii_footer = QLabel(_ASCII_HTML)
        self._ascii_footer.setTextFormat(Qt.TextFormat.RichText)
        self._ascii_footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ascii_footer.setStyleSheet("background: transparent;")
        self._cards_layout.addWidget(self._ascii_footer)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        scroll.setWidget(cards_container)
        splitter.addWidget(scroll)

        # Right panel: speed + progress
        right_panel = QWidget()
        right_panel.setFixedWidth(220)
        right_panel.setStyleSheet(
            "background: #161625; border-left: 1px solid #1E1E38; border-radius: 0;"
        )
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(12)
        self._rate_widget = TransferRateWidget()
        right_layout.addWidget(self._rate_widget)
        self._progress_panel = ProgressPanel()
        right_layout.addWidget(self._progress_panel, 1)
        splitter.addWidget(right_panel)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        root.addWidget(splitter, 1)

    def _connect_signals(self):
        self._registry.remote_added.connect(self._on_remote_added)
        self._registry.remote_removed.connect(self._on_remote_removed)
        self._sync.job_status_changed.connect(self._on_status_changed)
        self._sync.progress_updated.connect(self._on_progress)
        self._sync.file_transferred.connect(self._on_file_transferred)
        self._sync.any_job_active.connect(self._btn_pause_all.setEnabled)
        if self._mount:
            self._mount.mount_status_changed.connect(self._on_status_changed)
            self._mount.mount_failed.connect(lambda rid, err: self._on_mount_error(rid, err))

    def _load_existing_remotes(self):
        for rc in self._registry.list_remotes():
            self._add_card(rc)

    def _add_card(self, rc: RemoteConfig):
        if rc.remote_id in self._cards:
            return
        card = SyncStatusCard(rc, self)
        card.sync_requested.connect(self._start_remote)
        card.stop_requested.connect(self._sync.stop_job)
        card.mount_requested.connect(self._start_mount)
        card.unmount_requested.connect(self._stop_mount)
        card.settings_requested.connect(self._open_remote_settings)
        self._cards[rc.remote_id] = card

        # Remove empty label on first card
        if self._empty_label.isVisible():
            self._empty_label.hide()

        # Insert before the stretch (which is second-to-last) and ascii footer (last)
        count = self._cards_layout.count()
        self._cards_layout.insertWidget(count - 2, card)

    def _on_remote_added(self, rc: RemoteConfig):
        self._add_card(rc)

    def _on_remote_removed(self, remote_id: str):
        card = self._cards.pop(remote_id, None)
        if card:
            self._cards_layout.removeWidget(card)
            card.deleteLater()
        if not self._cards:
            self._empty_label.show()

    def _on_status_changed(self, job_id: str, status_value: str):
        # Find card by job_id (job_id == remote_id for remote-triggered jobs)
        card = self._cards.get(job_id)
        if card:
            card.update_status(JobStatus(status_value))

    def _on_progress(self, job_id: str, stats: TransferStats):
        card = self._cards.get(job_id)
        if card:
            card.update_progress(stats)
        self._rate_widget.update_speed(stats.speed_bps)
        if stats.bytes_total > 0:
            pct = stats.bytes_done / stats.bytes_total * 100
            self._progress_panel.update_aggregate_progress(pct)

    def _on_file_transferred(self, job_id: str, filename: str):
        self._progress_panel.add_file(job_id, filename)

    def _start_remote(self, remote_id: str):
        rc = self._registry.get_remote(remote_id)
        if rc.sync_mode == SyncMode.MOUNT:
            self._start_mount(remote_id)
        else:
            job = rc.to_sync_job()
            self._sync.start_job(job)

    def _start_mount(self, remote_id: str):
        if not self._mount:
            return
        from pathlib import Path

        rc = self._registry.get_remote(remote_id)
        mountpoint = Path(rc.local_path)
        self._mount.mount(
            remote_id,
            rc.remote_path,
            mountpoint,
            rc.mount_cache_mode,
            rc.mount_cache_size,
        )

    def _stop_mount(self, remote_id: str):
        if self._mount:
            self._mount.unmount(remote_id)

    def _on_mount_error(self, remote_id: str, error: str):
        from PySide6.QtWidgets import QMessageBox

        card = self._cards.get(remote_id)
        rc_name = card.remote.display_name if card else remote_id
        QMessageBox.warning(
            self,
            "Mount Error",
            f"Failed to mount '{rc_name}':\n\n{error}\n\n"
            "Make sure FUSE is installed:\n  sudo apt install fuse3",
        )

    def _sync_all(self):
        for rc in self._registry.list_remotes():
            if rc.is_enabled:
                self._start_remote(rc.remote_id)

    def _pause_all(self):
        for job_id in self._sync.active_job_ids():
            self._sync.pause_job(job_id)

    def _open_remote_settings(self, remote_id: str):
        self.remote_settings_requested.emit(remote_id)
