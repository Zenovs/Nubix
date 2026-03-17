"""Transfer rate widget with speed display and sparkline."""

from __future__ import annotations

import collections
import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


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
        self.setFixedHeight(48)
        self._data: collections.deque[float] = collections.deque(maxlen=60)
        self._line_color = QColor("#7C5CFC")
        self._fill_start = QColor(124, 92, 252, 80)
        self._fill_end = QColor(124, 92, 252, 0)

    def push(self, bps: float):
        self._data.append(bps)
        self.update()

    def paintEvent(self, event):
        if len(self._data) < 2:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        max_val = max(self._data) or 1

        points = list(self._data)
        n = len(points)
        step = w / max(n - 1, 1)
        coords = [(i * step, h - (v / max_val) * (h - 6) - 3) for i, v in enumerate(points)]

        # Fill area under curve
        from PySide6.QtGui import QPolygonF
        from PySide6.QtCore import QPointF

        poly = QPolygonF()
        poly.append(QPointF(coords[0][0], h))
        for x, y in coords:
            poly.append(QPointF(x, y))
        poly.append(QPointF(coords[-1][0], h))

        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0, self._fill_start)
        grad.setColorAt(1, self._fill_end)
        painter.setBrush(grad)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(poly)

        # Draw line
        pen = QPen(self._line_color, 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for i in range(1, len(coords)):
            painter.drawLine(
                int(coords[i - 1][0]),
                int(coords[i - 1][1]),
                int(coords[i][0]),
                int(coords[i][1]),
            )


class TransferRateWidget(QWidget):
    """Shows current download speed as text + sparkline."""

    _UPDATE_INTERVAL = 5.0  # seconds between display refreshes

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._last_update: float = 0.0

        header = QLabel("Transfer Speed")
        header.setStyleSheet(
            "color: #8888AA; font-size: 11px; font-weight: 600;"
            " letter-spacing: 1px; text-transform: uppercase; background: transparent;"
        )
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._label = QLabel("0 B/s")
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        self._label.setFont(font)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet("color: #7C5CFC; background: transparent;")

        self._sparkline = _SparklineWidget(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(header)
        layout.addWidget(self._label)
        layout.addWidget(self._sparkline)

    def update_speed(self, bps: float) -> None:
        now = time.monotonic()
        if now - self._last_update >= self._UPDATE_INTERVAL:
            self._last_update = now
            self._label.setText(_format_speed(bps))
            self._sparkline.push(bps)
