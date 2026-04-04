"""Update notification and download dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from nubix.core.updater import ReleaseInfo, Updater


class UpdateDialog(QDialog):
    """Shows release notes and lets the user download the update."""

    def __init__(self, release: ReleaseInfo, updater: Updater, parent=None):
        super().__init__(parent)
        self._release = release
        self._updater = updater
        self.setWindowTitle("Update Available — Nubix")
        self.setMinimumWidth(480)
        self._build_ui()
        self._connect()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(
            QLabel(
                f"<h3>Nubix {self._release.version} is available</h3>"
                f"<p>You are running version "
                f"<b>{self._updater.current_version}</b>.</p>"
            )
        )

        notes = QTextBrowser()
        notes.setMarkdown(self._release.body or "_No release notes provided._")
        notes.setMaximumHeight(200)
        layout.addWidget(notes)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setTextVisible(True)
        self._progress.hide()
        layout.addWidget(self._progress)

        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.hide()
        layout.addWidget(self._status_label)

        btns = QDialogButtonBox()
        self._btn_update = QPushButton("Download & Install Update")
        self._btn_update.setDefault(True)
        self._btn_update.setStyleSheet(
            "QPushButton { background: #4A90D9; color: white; border: none; "
            "padding: 8px 18px; border-radius: 6px; font-weight: bold; }"
            "QPushButton:hover { background: #1976D2; }"
        )
        btns.addButton(self._btn_update, QDialogButtonBox.ButtonRole.AcceptRole)

        self._btn_skip = QPushButton("Remind Me Later")
        btns.addButton(self._btn_skip, QDialogButtonBox.ButtonRole.RejectRole)

        layout.addWidget(btns)
        self._btn_update.clicked.connect(self._start_download)
        self._btn_skip.clicked.connect(self.reject)

    def _connect(self):
        self._updater.download_progress.connect(self._on_progress)
        self._updater.download_complete.connect(self._on_complete)
        self._updater.update_failed.connect(self._on_failed)
        self._updater.restart_required.connect(self._on_restart)

    def _start_download(self):
        self._btn_update.setEnabled(False)
        self._btn_skip.setEnabled(False)
        self._progress.show()
        self._progress.setValue(0)
        self._status_label.show()
        self._status_label.setText("Downloading update…")
        self._updater.download_and_apply(self._release)

    def _on_progress(self, pct: int):
        self._progress.setValue(pct)
        self._status_label.setText(f"Downloading… {pct}%")

    def _on_complete(self):
        self._progress.setValue(100)
        self._status_label.setText("Download complete!")

    def _on_failed(self, error: str):
        self._status_label.setText(f"Error: {error}")
        self._status_label.setStyleSheet("color: #D32F2F;")
        self._btn_skip.setEnabled(True)

    def _on_restart(self):
        self._status_label.setText("Update installed! Restarting…")
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication

        QApplication.processEvents()  # flush the label update to screen

        def _do_restart():
            import os
            import sys

            appimage = os.environ.get("APPIMAGE")
            if appimage:
                os.execv(appimage, [appimage] + sys.argv[1:])
            elif getattr(sys, "frozen", False):
                os.execv(sys.executable, [sys.executable] + sys.argv)
            else:
                # Source install: re-exec python with the original main.py
                main_py = str(__import__("pathlib").Path(sys.argv[0]).resolve())
                os.execv(sys.executable, [sys.executable, main_py] + sys.argv[1:])

        QTimer.singleShot(400, _do_restart)
