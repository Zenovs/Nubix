"""Recent file transfers panel."""

from __future__ import annotations

import collections
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from nubix.constants import MAX_RECENT_FILES


class ProgressPanel(QWidget):
    """Shows aggregate progress and recently transferred files."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._recent: collections.deque[dict] = collections.deque(maxlen=MAX_RECENT_FILES)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Aggregate progress bar
        agg_row = QHBoxLayout()
        agg_row.addWidget(QLabel("<b>Overall Progress</b>"))
        self._agg_bar = QProgressBar()
        self._agg_bar.setRange(0, 100)
        self._agg_bar.setValue(0)
        self._agg_bar.setTextVisible(True)
        self._agg_bar.setStyleSheet(
            "QProgressBar { border: none; border-radius: 4px; background: #e0e0e0; height: 12px; }"
            "QProgressBar::chunk { border-radius: 4px; background: #4A90D9; }"
        )
        agg_row.addWidget(self._agg_bar, 1)
        layout.addLayout(agg_row)

        # Recent files header
        layout.addWidget(QLabel("<b>Recent Transfers</b>"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        self._list_widget = QWidget()
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
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(4, 2, 4, 2)

        time_lbl = QLabel(now)
        time_lbl.setStyleSheet("color: #888; font-size: 11px; min-width: 60px;")
        row_layout.addWidget(time_lbl)

        file_lbl = QLabel(filename)
        file_lbl.setStyleSheet("font-size: 11px;")
        file_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row_layout.addWidget(file_lbl, 1)

        # Insert before the stretch (last item)
        count = self._list_layout.count()
        self._list_layout.insertWidget(count - 1, row)

        # Remove oldest if over limit
        if self._list_layout.count() > MAX_RECENT_FILES + 1:
            item = self._list_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
