"""Wizard welcome page."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWizardPage


class WelcomePage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Welcome to Nubix")
        self.setSubTitle("Connect your cloud storage in a few simple steps.")

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        info = QLabel(
            "<p>Nubix lets you sync files between your computer and cloud services "
            "like Google Drive, Dropbox, and Nextcloud.</p>"
            "<p>This wizard will help you add a new cloud connection. "
            "You will need to sign in to your cloud account in the next steps.</p>"
            "<p><b>Your credentials are stored locally</b> — Nubix never sends "
            "your data to any external server other than the cloud provider you choose.</p>"
        )
        info.setWordWrap(True)
        info.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(info)
        layout.addStretch()
