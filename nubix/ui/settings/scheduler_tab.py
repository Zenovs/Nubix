"""Scheduler settings tab — per-remote time windows."""

from __future__ import annotations

from datetime import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from nubix.core.remote_registry import RemoteRegistry
from nubix.core.scheduler import Scheduler
from nubix.core.sync_job import TimeWindow

_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class SchedulerTab(QWidget):
    def __init__(self, registry: RemoteRegistry, scheduler: Scheduler, parent=None):
        super().__init__(parent)
        self._registry = registry
        self._scheduler = scheduler
        self._build_ui()
        self._load_remotes()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Remote list
        self._remote_list = QListWidget()
        self._remote_list.currentRowChanged.connect(self._on_remote_selected)
        splitter.addWidget(self._remote_list)

        # Schedule settings panel
        right = QWidget()
        right_layout = QVBoxLayout(right)

        right_layout.addWidget(QLabel("<b>Sync only during these hours:</b>"))

        # Day checkboxes
        days_row = QHBoxLayout()
        self._day_checks: list[QCheckBox] = []
        for day in _DAYS:
            cb = QCheckBox(day)
            days_row.addWidget(cb)
            self._day_checks.append(cb)
        right_layout.addLayout(days_row)

        # Time range
        time_row = QHBoxLayout()
        time_row.addWidget(QLabel("From:"))
        self._start_time = QTimeEdit()
        self._start_time.setDisplayFormat("HH:mm")
        time_row.addWidget(self._start_time)
        time_row.addWidget(QLabel("To:"))
        self._end_time = QTimeEdit()
        self._end_time.setDisplayFormat("HH:mm")
        time_row.addWidget(self._end_time)
        time_row.addStretch()
        right_layout.addLayout(time_row)

        self._enable_schedule = QCheckBox("Enable schedule for this connection")
        right_layout.addWidget(self._enable_schedule)
        right_layout.addStretch()

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

    def _load_remotes(self):
        for rc in self._registry.list_remotes():
            item = QListWidgetItem(rc.display_name)
            item.setData(Qt.ItemDataRole.UserRole, rc.remote_id)
            self._remote_list.addItem(item)

    def _on_remote_selected(self, row: int):
        if row < 0:
            return
        item = self._remote_list.item(row)
        if not item:
            return
        remote_id = item.data(Qt.ItemDataRole.UserRole)
        rc = self._registry.get_remote(remote_id)
        self._enable_schedule.setChecked(rc.is_scheduled)
        if rc.is_scheduled and rc.to_sync_job().schedule_windows:
            w = rc.to_sync_job().schedule_windows[0]
            for i, cb in enumerate(self._day_checks):
                cb.setChecked(i in w.days)
            t = self._start_time.time()
            self._start_time.setTime(
                __import__("PySide6.QtCore", fromlist=["QTime"]).QTime(
                    w.start_time.hour, w.start_time.minute
                )
            )
            self._end_time.setTime(
                __import__("PySide6.QtCore", fromlist=["QTime"]).QTime(
                    w.end_time.hour, w.end_time.minute
                )
            )

    def save(self):
        item = self._remote_list.currentItem()
        if not item:
            return
        remote_id = item.data(Qt.ItemDataRole.UserRole)
        rc = self._registry.get_remote(remote_id)
        data = rc.to_dict()
        data["is_scheduled"] = self._enable_schedule.isChecked()
        self._registry.update_remote(remote_id, data)
