"""Colored pill-shaped status badge widget."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from nubix.core.sync_job import JobStatus

_STATUS_STYLES = {
    JobStatus.IDLE: ("Idle", "#888888", "#f0f0f0"),
    JobStatus.SYNCING: ("Syncing", "#1976D2", "#E3F2FD"),
    JobStatus.PAUSED: ("Paused", "#F57C00", "#FFF3E0"),
    JobStatus.ERROR: ("Error", "#D32F2F", "#FFEBEE"),
    JobStatus.UP_TO_DATE: ("Up to date", "#388E3C", "#E8F5E9"),
}


class StatusBadge(QLabel):
    """Small colored pill label showing sync status."""

    def __init__(self, status: JobStatus = JobStatus.IDLE, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_status(status)

    def set_status(self, status: JobStatus) -> None:
        text, fg, bg = _STATUS_STYLES.get(status, ("Unknown", "#666", "#eee"))
        self.setText(text)
        self.setStyleSheet(
            f"QLabel {{ "
            f"  color: {fg}; background: {bg}; border: 1px solid {fg}; "
            f"  border-radius: 10px; padding: 2px 10px; font-size: 11px; font-weight: bold; "
            f"}}"
        )
