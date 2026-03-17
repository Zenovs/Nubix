"""Bandwidth settings tab."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from nubix.core.bandwidth_controller import (
    BandwidthController,
    format_for_display,
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

        info = QLabel(
            "Limit how much bandwidth Nubix uses for cloud sync. " "Set to 0 for unlimited."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self._upload_slider = _SpeedSlider("Upload limit")
        layout.addWidget(self._upload_slider)

        self._download_slider = _SpeedSlider("Download limit")
        layout.addWidget(self._download_slider)

        layout.addStretch()

    def _load(self):
        self._upload_slider.set_from_rclone(self._ctrl.upload_limit)
        self._download_slider.set_from_rclone(self._ctrl.download_limit)

    def save(self):
        self._ctrl.set_upload_limit(self._upload_slider.get_rclone_value())
        self._ctrl.set_download_limit(self._download_slider.get_rclone_value())
