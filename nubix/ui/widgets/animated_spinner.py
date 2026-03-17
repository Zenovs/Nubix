"""Pure-QPainter rotating arc spinner widget."""

from __future__ import annotations

import math

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class AnimatedSpinner(QWidget):
    """A smooth animated spinner for indicating ongoing activity."""

    def __init__(self, size: int = 24, color: str = "#7C5CFC", parent=None):
        super().__init__(parent)
        self._size = size
        self._color = QColor(color)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
        self.setFixedSize(size, size)
        self.hide()

    def start(self):
        self._timer.start(30)
        self.show()

    def stop(self):
        self._timer.stop()
        self.hide()

    def _rotate(self):
        self._angle = (self._angle + 12) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(self._size / 2, self._size / 2)
        painter.rotate(self._angle)

        pen = QPen(self._color, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        r = self._size / 2 - 3
        painter.drawArc(int(-r), int(-r), int(r * 2), int(r * 2), 0, 270 * 16)
