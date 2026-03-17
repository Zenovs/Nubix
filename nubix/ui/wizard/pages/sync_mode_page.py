"""Wizard page: choose sync mode."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QLabel,
    QRadioButton,
    QVBoxLayout,
    QWizardPage,
)

from nubix.core.sync_job import SyncMode

_MODES = [
    (
        SyncMode.FULL,
        "Full Sync (Download Everything)",
        "All files are downloaded and available offline. Uses the most disk space.",
    ),
    (SyncMode.SELECTIVE, "Selective Sync", "Choose which folders to download. Saves disk space."),
    (
        SyncMode.BIDIRECTIONAL,
        "Bidirectional Sync",
        "Changes on your computer are uploaded, and changes in the cloud are downloaded.",
    ),
]


class SyncModePage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Choose Sync Mode")
        self.setSubTitle("How should Nubix synchronize your files?")

        self._group = QButtonGroup(self)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        for i, (mode, title, description) in enumerate(_MODES):
            radio = QRadioButton(title)
            if i == 0:
                radio.setChecked(True)
            self._group.addButton(radio, i)
            layout.addWidget(radio)

            desc = QLabel(f"    {description}")
            desc.setStyleSheet("color: #666; font-size: 11px;")
            desc.setWordWrap(True)
            layout.addWidget(desc)

        layout.addStretch()

        self.registerField("sync_mode", self, "sync_mode_value", self._group.idToggled)

    def _get_sync_mode_value(self) -> str:
        idx = self._group.checkedId()
        if idx < 0:
            return SyncMode.FULL.value
        return _MODES[idx][0].value

    def _set_sync_mode_value(self, val: str):
        pass

    sync_mode_value = property(_get_sync_mode_value, _set_sync_mode_value)

    def isComplete(self) -> bool:
        return self._group.checkedButton() is not None
