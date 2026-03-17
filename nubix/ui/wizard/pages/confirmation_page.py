"""Wizard confirmation page — summary before finishing."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QFormLayout, QLabel, QVBoxLayout, QWizardPage

from nubix.core.sync_job import SyncMode


class ConfirmationPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Ready to Connect")
        self.setSubTitle("Review your settings and click Finish to start syncing.")

        layout = QVBoxLayout(self)

        self._form = QFormLayout()
        self._provider_lbl = QLabel()
        self._path_lbl = QLabel()
        self._mode_lbl = QLabel()
        self._form.addRow("Provider:", self._provider_lbl)
        self._form.addRow("Local folder:", self._path_lbl)
        self._form.addRow("Sync mode:", self._mode_lbl)
        layout.addLayout(self._form)
        layout.addSpacing(16)

        self._start_now = QCheckBox("Start syncing immediately after setup")
        self._start_now.setChecked(True)
        layout.addWidget(self._start_now)
        layout.addStretch()

    def initializePage(self):
        provider_id = self.wizard().field("provider_id") or ""
        local_path = self.wizard().field("local_path") or ""
        sync_mode = self.wizard().field("sync_mode_value") or SyncMode.FULL.value

        mode_labels = {
            SyncMode.FULL.value: "Full Sync (Download Everything)",
            SyncMode.SELECTIVE.value: "Selective Sync",
            SyncMode.BIDIRECTIONAL.value: "Bidirectional Sync",
        }
        provider_names = {
            "gdrive": "Google Drive",
            "dropbox": "Dropbox",
            "nextcloud": "Nextcloud",
        }

        self._provider_lbl.setText(provider_names.get(provider_id, provider_id))
        self._path_lbl.setText(local_path)
        self._mode_lbl.setText(mode_labels.get(sync_mode, sync_mode))

    def should_start_now(self) -> bool:
        return self._start_now.isChecked()
