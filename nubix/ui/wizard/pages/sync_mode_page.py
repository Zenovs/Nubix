"""Wizard page: choose sync mode."""

from __future__ import annotations

from PySide6.QtCore import Property, Qt, Signal
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
        "Full Sync",
        "All files are synced in both directions — uploads local changes and downloads cloud changes.",
    ),
    (
        SyncMode.SELECTIVE,
        "Selective Sync",
        "Choose which folders to sync. Changes go both ways — uploads and downloads.",
    ),
    (
        SyncMode.BIDIRECTIONAL,
        "Bidirectional Sync",
        "Same as Full Sync with advanced conflict resolution options.",
    ),
    (
        SyncMode.MOUNT,
        "Mount (On-Demand)",
        "Files appear in your file manager but are only downloaded when you open them. Saves disk space — no local copy kept.",
    ),
]


class SyncModePage(QWizardPage):
    # changedSignal must belong to the page itself, not a child widget
    _sync_mode_changed = Signal(str)

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

        self._group.idToggled.connect(
            lambda _id, _checked: self._sync_mode_changed.emit(self._get_sync_mode_value())
        )

        # Field name "sync_mode_value" matches all wizard.field("sync_mode_value") calls
        self.registerField("sync_mode_value", self, "sync_mode_value", self._sync_mode_changed)

    def _get_sync_mode_value(self) -> str:
        idx = self._group.checkedId()
        if idx < 0:
            return SyncMode.FULL.value
        return _MODES[idx][0].value

    def _set_sync_mode_value(self, val: str):
        pass

    # Qt Property so QWizard.field() can read it via the meta-object system
    sync_mode_value = Property(
        str, _get_sync_mode_value, _set_sync_mode_value, notify=_sync_mode_changed
    )

    def isComplete(self) -> bool:
        return self._group.checkedButton() is not None
