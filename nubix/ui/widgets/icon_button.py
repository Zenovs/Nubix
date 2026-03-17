"""Square icon-only push button."""

from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QPushButton


class IconButton(QPushButton):
    """A square QPushButton with an icon and optional tooltip."""

    def __init__(self, icon: QIcon, tooltip: str = "", size: int = 32, parent=None):
        super().__init__(parent)
        self.setIcon(icon)
        self.setFixedSize(size, size)
        self.setIconSize(QSize(size - 8, size - 8))
        if tooltip:
            self.setToolTip(tooltip)
        self.setFlat(True)
        self.setStyleSheet(
            "QPushButton { border: none; border-radius: 6px; }"
            "QPushButton:hover { background: rgba(0,0,0,0.08); }"
            "QPushButton:pressed { background: rgba(0,0,0,0.15); }"
        )
