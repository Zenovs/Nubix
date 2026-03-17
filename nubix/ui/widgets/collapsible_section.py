"""Animated collapsible section widget."""

from __future__ import annotations

from PySide6.QtCore import QPropertyAnimation, QAbstractAnimation, Qt
from PySide6.QtWidgets import QFrame, QToolButton, QVBoxLayout, QWidget, QSizePolicy


class CollapsibleSection(QWidget):
    """An expandable/collapsible panel with animated transition."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._toggle = QToolButton(self)
        self._toggle.setText(title)
        self._toggle.setCheckable(True)
        self._toggle.setChecked(False)
        self._toggle.setStyleSheet(
            "QToolButton { border: none; font-weight: bold; padding: 4px; }"
            "QToolButton::indicator { width: 0; }"
        )
        self._toggle.setArrowType(Qt.ArrowType.RightArrow)
        self._toggle.clicked.connect(self._on_toggle)

        self._content = QFrame(self)
        self._content.setFrameShape(QFrame.Shape.NoFrame)
        self._content.setMaximumHeight(0)
        self._content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._animation = QPropertyAnimation(self._content, b"maximumHeight")
        self._animation.setDuration(200)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._toggle)
        layout.addWidget(self._content)

        self._inner_layout = QVBoxLayout(self._content)
        self._inner_layout.setContentsMargins(8, 4, 8, 4)

    def set_content_widget(self, widget: QWidget) -> None:
        self._inner_layout.addWidget(widget)
        # Set collapsed height hint after content is set
        self._content.adjustSize()

    def _on_toggle(self, checked: bool):
        self._toggle.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
        target = self._content.sizeHint().height() if checked else 0
        self._animation.stop()
        self._animation.setStartValue(self._content.maximumHeight())
        self._animation.setEndValue(target)
        self._animation.start()
