"""Log viewer widget."""

from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtCore import Qt, QMetaObject, Q_ARG
from PySide6.QtGui import QColor, QTextCursor, QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

_LEVEL_COLORS = {
    logging.DEBUG: "#888888",
    logging.INFO: "#333333",
    logging.WARNING: "#F57C00",
    logging.ERROR: "#D32F2F",
    logging.CRITICAL: "#B71C1C",
}


class _QtLogHandler(logging.Handler):
    """Routes log records to the LogViewer via thread-safe signal."""

    def __init__(self, viewer: "LogViewer"):
        super().__init__()
        self._viewer = viewer

    def emit(self, record: logging.LogRecord):
        msg = self.format(record)
        # Thread-safe call to append text in the UI thread
        QMetaObject.invokeMethod(
            self._viewer,
            "_append_line",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, msg),
            Q_ARG(int, record.levelno),
        )


class LogViewer(QWidget):
    """Read-only log viewer with export capability."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._install_handler()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        toolbar = QHBoxLayout()
        btn_clear = QPushButton("Clear")
        btn_clear.setFixedWidth(70)
        btn_clear.clicked.connect(self._clear)
        toolbar.addStretch()
        toolbar.addWidget(btn_clear)

        btn_export = QPushButton("Export…")
        btn_export.setFixedWidth(80)
        btn_export.clicked.connect(self._export)
        toolbar.addWidget(btn_export)
        layout.addLayout(toolbar)

        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        font = QFont("Monospace", 10)
        self._text.setFont(font)
        self._text.setMaximumBlockCount(5000)
        self._auto_scroll = True
        self._text.verticalScrollBar().valueChanged.connect(self._on_scroll_change)
        layout.addWidget(self._text, 1)

    def _install_handler(self):
        handler = _QtLogHandler(self)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        logging.getLogger().addHandler(handler)

    def _append_line(self, msg: str, level: int):
        color = _LEVEL_COLORS.get(level, "#333")
        cursor = self._text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._text.setTextCursor(cursor)
        self._text.appendPlainText(msg)
        if self._auto_scroll:
            self._text.verticalScrollBar().setValue(self._text.verticalScrollBar().maximum())

    def _on_scroll_change(self, value: int):
        max_val = self._text.verticalScrollBar().maximum()
        self._auto_scroll = value >= max_val - 10

    def _clear(self):
        self._text.clear()

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Log",
            f"nubix_log_{datetime.now():%Y%m%d_%H%M%S}.txt",
            "Text files (*.txt)",
        )
        if path:
            with open(path, "w") as f:
                f.write(self._text.toPlainText())
