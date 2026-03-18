"""Bandwidth settings tab."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTime
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from nubix.core.bandwidth_controller import (
    BandwidthController,
    mbps_to_rclone,
    rclone_to_mbps,
)

_MAX_MBPS = 100


class _SpeedSlider(QWidget):
    """A labeled speed slider (0 to MAX_MBPS MB/s)."""

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)

        row.addWidget(QLabel(f"<b>{label}</b>"))

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, _MAX_MBPS * 10)  # 0.1 MB/s steps
        self._slider.setValue(0)
        self._slider.setTickInterval(100)
        row.addWidget(self._slider, 1)

        self._value_lbl = QLabel("Unlimited")
        self._value_lbl.setFixedWidth(90)
        self._value_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self._value_lbl)

        self._slider.valueChanged.connect(self._update_label)

    def _update_label(self, val: int):
        if val == 0:
            self._value_lbl.setText("Unlimited")
        else:
            mbps = val / 10.0
            if mbps < 1:
                self._value_lbl.setText(f"{mbps * 1024:.0f} KB/s")
            else:
                self._value_lbl.setText(f"{mbps:.1f} MB/s")

    def get_rclone_value(self) -> str:
        val = self._slider.value()
        if val == 0:
            return "0"
        return mbps_to_rclone(val / 10.0)

    def set_from_rclone(self, limit_str: str):
        mbps = rclone_to_mbps(limit_str)
        self._slider.setValue(int(mbps * 10))


class BandwidthTab(QWidget):
    def __init__(self, controller: BandwidthController, parent=None):
        super().__init__(parent)
        self._ctrl = controller
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        # ── Global limits ──────────────────────────────────────────────
        global_group = QGroupBox("Global limits")
        gl = QVBoxLayout(global_group)
        gl.setSpacing(12)

        info = QLabel("Applied when no bandwidth schedule is active.  Set to 0 for unlimited.")
        info.setWordWrap(True)
        gl.addWidget(info)

        self._upload_slider = _SpeedSlider("Upload")
        gl.addWidget(self._upload_slider)

        self._download_slider = _SpeedSlider("Download")
        gl.addWidget(self._download_slider)

        layout.addWidget(global_group)

        # ── Bandwidth schedule ─────────────────────────────────────────
        sched_group = QGroupBox("Bandwidth schedule")
        sl = QVBoxLayout(sched_group)
        sl.setSpacing(12)

        self._sched_cb = QCheckBox("Limit bandwidth during specific hours")
        sl.addWidget(self._sched_cb)

        self._sched_widget = QWidget()
        sw = QVBoxLayout(self._sched_widget)
        sw.setContentsMargins(0, 4, 0, 0)
        sw.setSpacing(10)

        # Time range row
        time_row = QHBoxLayout()
        time_row.addWidget(QLabel("Limit from"))
        self._from_time = QTimeEdit()
        self._from_time.setDisplayFormat("HH:mm")
        self._from_time.setFixedWidth(70)
        time_row.addWidget(self._from_time)
        time_row.addWidget(QLabel("to"))
        self._to_time = QTimeEdit()
        self._to_time.setDisplayFormat("HH:mm")
        self._to_time.setFixedWidth(70)
        time_row.addWidget(self._to_time)
        time_row.addStretch()
        sw.addLayout(time_row)

        self._sched_upload = _SpeedSlider("Upload")
        sw.addWidget(self._sched_upload)

        self._sched_download = _SpeedSlider("Download")
        sw.addWidget(self._sched_download)

        note = QLabel("Outside this window: unlimited (no limit)")
        note.setStyleSheet("color: #8888AA; font-style: italic; font-size: 11px;")
        sw.addWidget(note)

        sl.addWidget(self._sched_widget)
        layout.addWidget(sched_group)

        layout.addStretch()

        self._sched_cb.toggled.connect(self._sched_widget.setEnabled)

    def _load(self):
        self._upload_slider.set_from_rclone(self._ctrl.upload_limit)
        self._download_slider.set_from_rclone(self._ctrl.download_limit)

        self._sched_cb.setChecked(self._ctrl.schedule_enabled)
        self._sched_widget.setEnabled(self._ctrl.schedule_enabled)

        def _parse_time(hhmm: str) -> QTime:
            parts = hhmm.split(":")
            try:
                return QTime(int(parts[0]), int(parts[1]))
            except Exception:
                return QTime(8, 0)

        self._from_time.setTime(_parse_time(self._ctrl.schedule_from))
        self._to_time.setTime(_parse_time(self._ctrl.schedule_to))
        self._sched_upload.set_from_rclone(self._ctrl.schedule_upload_limit)
        self._sched_download.set_from_rclone(self._ctrl.schedule_download_limit)

    def save(self):
        self._ctrl.set_upload_limit(self._upload_slider.get_rclone_value())
        self._ctrl.set_download_limit(self._download_slider.get_rclone_value())

        ft = self._from_time.time()
        tt = self._to_time.time()
        self._ctrl.set_schedule(
            enabled=self._sched_cb.isChecked(),
            from_time=f"{ft.hour():02d}:{ft.minute():02d}",
            to_time=f"{tt.hour():02d}:{tt.minute():02d}",
            upload=self._sched_upload.get_rclone_value(),
            download=self._sched_download.get_rclone_value(),
        )
