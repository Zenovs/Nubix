"""Colored pill-shaped status badge widget."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from nubix.core.sync_job import JobStatus

_STATUS_STYLES = {
    JobStatus.IDLE: ("Idle", "#6B7280", "#1A1A2A"),
    JobStatus.SYNCING: ("Syncing", "#60A5FA", "#0A1A30"),
    JobStatus.PAUSED: ("Paused", "#FB923C", "#2A1500"),
    JobStatus.ERROR: ("Error", "#F87171", "#2A0A0A"),
    JobStatus.UP_TO_DATE: ("Up to date", "#4ADE80", "#0D2A1A"),
    JobStatus.MOUNTED: ("Mounted", "#A78BFA", "#1A0A40"),
}


class StatusBadge(QLabel):
    """Small colored pill label showing sync status."""

    def __init__(self, status: JobStatus = JobStatus.IDLE, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_status(status)

    def set_status(self, status: JobStatus) -> None:
        text, fg, bg = _STATUS_STYLES.get(status, ("Unknown", "#6B7280", "#1A1A2A"))
        self.setText(text)
        self.setStyleSheet(
            f"QLabel {{ "
            f"  color: {fg}; background: {bg}; border: 1px solid {fg}40; "
            f"  border-radius: 10px; padding: 3px 12px; font-size: 11px; font-weight: 700; "
            f"}}"
        )
