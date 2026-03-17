"""Wizard provider selection page."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QGridLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWizardPage,
)

_PROVIDERS = [
    ("gdrive", "Google Drive", "☁"),
    ("dropbox", "Dropbox", "📦"),
    ("nextcloud", "Nextcloud", "🔒"),
]


class ProviderSelectPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Choose a Cloud Provider")
        self.setSubTitle("Select the service you want to connect.")

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        layout = QVBoxLayout(self)
        grid = QGridLayout()
        grid.setSpacing(12)

        self._buttons: dict[str, QToolButton] = {}
        for col, (pid, name, icon) in enumerate(_PROVIDERS):
            btn = QToolButton()
            btn.setText(f"{icon}\n{name}")
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            btn.setCheckable(True)
            btn.setFixedSize(110, 90)
            btn.setStyleSheet(
                "QToolButton { border: 2px solid #ddd; border-radius: 8px; font-size: 13px; }"
                "QToolButton:checked { border-color: #4A90D9; background: #E3F2FD; }"
                "QToolButton:hover { border-color: #4A90D9; }"
            )
            self._group.addButton(btn, col)
            grid.addWidget(btn, 0, col)
            self._buttons[pid] = btn

        layout.addLayout(grid)
        layout.addStretch()

        # Register a dummy field; we read the button directly
        self.registerField("provider_id*", self, "provider_id", self._group.idToggled)

    def _get_provider_id(self) -> str:
        checked = self._group.checkedButton()
        if not checked:
            return ""
        idx = self._group.id(checked)
        return _PROVIDERS[idx][0]

    def _set_provider_id(self, val: str):
        pass  # read-only

    provider_id = property(_get_provider_id, _set_provider_id)

    def isComplete(self) -> bool:
        return self._group.checkedButton() is not None
