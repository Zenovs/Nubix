"""Recent file transfers panel."""

from __future__ import annotations

import collections
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
)

from nubix.constants import MAX_RECENT_FILES


class ProgressPanel(QWidget):
    """Shows aggregate progress and recently transferred files."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._recent: collections.deque[dict] = collections.deque(maxlen=MAX_RECENT_FILES)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Aggregate progress
        prog_header = QLabel("Overall Progress")
        prog_header.setStyleSheet(
            "color: #8888AA; font-size: 11px; font-weight: 600;"
            " letter-spacing: 1px; background: transparent;"
        )
        layout.addWidget(prog_header)

        self._agg_bar = QProgressBar()
        self._agg_bar.setRange(0, 100)
        self._agg_bar.setValue(0)
        self._agg_bar.setTextVisible(True)
        self._agg_bar.setFormat("%p%")
        self._agg_bar.setFixedHeight(10)
        self._agg_bar.setStyleSheet(
            "QProgressBar { border: none; border-radius: 5px; background: #2E2E50;"
            " color: #E2E2F0; font-size: 10px; }"
            "QProgressBar::chunk { border-radius: 5px;"
            " background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            " stop:0 #7C5CFC, stop:1 #A78BFA); }"
        )
        layout.addWidget(self._agg_bar)

        # Separator
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #1E1E38;")
        layout.addWidget(sep)

        # Recent files header
        recent_header = QLabel("Recent Transfers")
        recent_header.setStyleSheet(
            "color: #8888AA; font-size: 11px; font-weight: 600;"
            " letter-spacing: 1px; background: transparent;"
        )
        layout.addWidget(recent_header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        self._list_widget = QWidget()
        self._list_widget.setStyleSheet("background: transparent;")
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(2)
        self._list_layout.addStretch()
        scroll.setWidget(self._list_widget)
        layout.addWidget(scroll, 1)

    def update_aggregate_progress(self, percent: float) -> None:
        self._agg_bar.setValue(int(max(0, min(100, percent))))

    def add_file(self, job_id: str, filename: str) -> None:
        now = datetime.now().strftime("%H:%M:%S")
        entry = {"job_id": job_id, "filename": filename, "time": now}
        self._recent.appendleft(entry)

        row = QWidget()
        row.setStyleSheet(
            "QWidget { background: #1E1E32; border-radius: 6px; }"
            "QWidget:hover { background: #252542; }"
        )
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(6, 4, 6, 4)
        row_layout.setSpacing(6)

        time_lbl = QLabel(now)
        time_lbl.setStyleSheet(
            "color: #6B7280; font-size: 10px; min-width: 58px; background: transparent;"
        )
        row_layout.addWidget(time_lbl)

        file_lbl = QLabel(filename)
        file_lbl.setStyleSheet("color: #C0C0D8; font-size: 11px; background: transparent;")
        file_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row_layout.addWidget(file_lbl, 1)

        count = self._list_layout.count()
        self._list_layout.insertWidget(count - 1, row)

        if self._list_layout.count() > MAX_RECENT_FILES + 1:
            item = self._list_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
