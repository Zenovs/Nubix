"""Transfer rate widget with speed display and sparkline."""

from __future__ import annotations

import collections
import math

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen, QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


def _format_speed(bps: float) -> str:
    if bps <= 0:
        return "0 B/s"
    units = ["B/s", "KB/s", "MB/s", "GB/s"]
    i = 0
    while bps >= 1024 and i < len(units) - 1:
        bps /= 1024
        i += 1
    return f"{bps:.1f} {units[i]}"


class _SparklineWidget(QWidget):
    """Draws a mini sparkline graph of recent transfer speeds."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self._data: collections.deque[float] = collections.deque(maxlen=60)
        self._color = QColor("#4A90D9")

    def push(self, bps: float):
        self._data.append(bps)
        self.update()

    def paintEvent(self, event):
        if not self._data:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        max_val = max(self._data) or 1

        pen = QPen(self._color, 1.5)
        painter.setPen(pen)

        points = list(self._data)
        n = len(points)
        step = w / max(n - 1, 1)
        coords = [(i * step, h - (v / max_val) * (h - 4) - 2) for i, v in enumerate(points)]

        for i in range(1, len(coords)):
            painter.drawLine(
                int(coords[i - 1][0]),
                int(coords[i - 1][1]),
                int(coords[i][0]),
                int(coords[i][1]),
            )


class TransferRateWidget(QWidget):
    """Shows current download speed as text + sparkline."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._label = QLabel("0 B/s", self)
        font = QFont()
        font.setPointSize(13)
        font.setBold(True)
        self._label.setFont(font)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._sparkline = _SparklineWidget(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        layout.addWidget(self._label)
        layout.addWidget(self._sparkline)

    def update_speed(self, bps: float) -> None:
        self._label.setText(_format_speed(bps))
        self._sparkline.push(bps)
