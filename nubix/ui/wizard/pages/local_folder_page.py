"""Wizard page: choose local sync folder."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWizardPage,
)


class LocalFolderPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Choose Local Folder")
        self.setSubTitle("Select where synced files will be stored on your computer.")

        layout = QVBoxLayout(self)

        info = QLabel(
            "Files from the cloud will be downloaded to this folder. "
            "Choose an empty folder or create a new one."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        row = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("/home/user/CloudSync/MyDrive")
        self._path_edit.textChanged.connect(self.completeChanged)
        row.addWidget(self._path_edit, 1)

        btn_browse = QPushButton("Browse…")
        btn_browse.setFixedWidth(90)
        btn_browse.clicked.connect(self._browse)
        row.addWidget(btn_browse)
        layout.addLayout(row)

        self._warn_label = QLabel("")
        self._warn_label.setStyleSheet("color: #D32F2F; font-size: 11px;")
        layout.addWidget(self._warn_label)
        layout.addStretch()

        self.registerField("local_path*", self._path_edit)

    def initializePage(self):
        provider_id = self.wizard().field("provider_id") or "cloud"
        default = str(Path.home() / "Nubix" / provider_id.capitalize())
        self._path_edit.setText(default)

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "Select Sync Folder", str(Path.home()))
        if path:
            self._path_edit.setText(path)

    def isComplete(self) -> bool:
        text = self._path_edit.text().strip()
        if not text:
            self._warn_label.setText("")
            return False
        path = Path(text)
        if path.is_file():
            self._warn_label.setText("That path is a file, not a folder.")
            return False
        # Check parent is writable
        parent = path if path.exists() else path.parent
        if not parent.exists():
            self._warn_label.setText("")
            return True  # Will be created
        import os

        if not os.access(str(parent), os.W_OK):
            self._warn_label.setText("That folder is not writable.")
            return False
        self._warn_label.setText("")
        return True
