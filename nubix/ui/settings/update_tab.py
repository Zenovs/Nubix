"""Update tab for the Settings dialog."""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from nubix.core.updater import ReleaseInfo, Updater
from nubix import __version__


class UpdateTab(QWidget):
    """Settings tab for checking and installing updates."""

    def __init__(self, updater: Updater, parent=None):
        super().__init__(parent)
        self._updater = updater
        self._pending_release: ReleaseInfo | None = None
        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # ── Current version row ──
        version_row = QHBoxLayout()
        version_row.addWidget(QLabel("Current version:"))
        ver_lbl = QLabel(f"<b>v{__version__}</b>")
        ver_lbl.setStyleSheet("color: #7C5CFC;")
        version_row.addWidget(ver_lbl)
        version_row.addStretch()
        layout.addLayout(version_row)

        # ── Status label ──
        self._status = QLabel("Click 'Check for Updates' to look for a new release.")
        self._status.setWordWrap(True)
        self._status.setStyleSheet("color: #8888AA; font-size: 12px;")
        layout.addWidget(self._status)

        # ── Release notes box (hidden until update found) ──
        self._notes_label = QLabel("What's new:")
        self._notes_label.setStyleSheet("font-weight: 600;")
        self._notes_label.hide()
        layout.addWidget(self._notes_label)

        self._notes = QTextBrowser()
        self._notes.setMaximumHeight(180)
        self._notes.setStyleSheet(
            "QTextBrowser { background: #1E1E32; border: 1px solid #2E2E50;"
            " border-radius: 8px; color: #E2E2F0; padding: 8px; }"
        )
        self._notes.hide()
        layout.addWidget(self._notes)

        # ── Progress bar (hidden until downloading) ──
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setTextVisible(True)
        self._progress.setFormat("%p%  —  downloading…")
        self._progress.setFixedHeight(22)
        self._progress.hide()
        layout.addWidget(self._progress)

        layout.addStretch()

        # ── Buttons ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._btn_check = QPushButton("🔍   Check for Updates")
        self._btn_check.setFixedWidth(200)
        self._btn_check.clicked.connect(self._check)
        btn_row.addWidget(self._btn_check)

        self._btn_install = QPushButton("⬇   Download & Install")
        self._btn_install.setFixedWidth(200)
        self._btn_install.setStyleSheet(
            "QPushButton { background: #4ADE80; color: #0D2A1A; border: none;"
            " border-radius: 8px; padding: 8px 18px; font-weight: 700; }"
            "QPushButton:hover { background: #22c55e; }"
            "QPushButton:disabled { background: #1E1E32; color: #4A4A6A; }"
        )
        self._btn_install.hide()
        self._btn_install.clicked.connect(self._install)
        btn_row.addWidget(self._btn_install)

        self._btn_restart = QPushButton("🔄   Restart Now")
        self._btn_restart.setFixedWidth(200)
        self._btn_restart.setStyleSheet(
            "QPushButton { background: #7C5CFC; color: white; border: none;"
            " border-radius: 8px; padding: 8px 18px; font-weight: 700; }"
            "QPushButton:hover { background: #9070FF; }"
        )
        self._btn_restart.hide()
        self._btn_restart.clicked.connect(self._restart)
        btn_row.addWidget(self._btn_restart)

        layout.addLayout(btn_row)

    def _connect_signals(self):
        self._updater.update_available.connect(self._on_update_available)
        self._updater.no_update.connect(self._on_no_update)
        self._updater.check_failed.connect(self._on_check_failed)
        self._updater.download_progress.connect(self._on_progress)
        self._updater.download_complete.connect(self._on_download_complete)
        self._updater.update_failed.connect(self._on_update_failed)
        self._updater.restart_required.connect(self._on_restart_required)

    # ── Button actions ─────────────────────────────────────────────────────────

    def _check(self):
        self._btn_check.setEnabled(False)
        self._btn_install.hide()
        self._notes.hide()
        self._notes_label.hide()
        self._progress.hide()
        self._btn_restart.hide()
        self._set_status("🔍  Checking for updates…", "#8888AA")
        self._updater.check_for_updates()

    def _install(self):
        if not self._pending_release:
            return
        self._btn_install.setEnabled(False)
        self._btn_check.setEnabled(False)
        self._progress.setValue(0)
        self._progress.show()
        self._set_status("⬇  Downloading update…", "#60A5FA")
        self._updater.download_and_apply(self._pending_release)

    def _restart(self):
        # When running as AppImage, APPIMAGE points to the file on disk (already
        # replaced by the updater). sys.executable points to the Python binary
        # inside the OLD squashfs mount — exec'ing that would relaunch the old version.
        appimage = os.environ.get("APPIMAGE")
        if appimage:
            os.execv(appimage, [appimage])
        else:
            os.execv(sys.executable, [sys.executable] + sys.argv)

    # ── Updater signal handlers ────────────────────────────────────────────────

    def _on_update_available(self, release: ReleaseInfo):
        self._pending_release = release
        self._btn_check.setEnabled(True)
        self._set_status(f"🎉  Version <b>v{release.version}</b> is available!", "#4ADE80")
        if release.body:
            self._notes.setMarkdown(release.body)
            self._notes_label.show()
            self._notes.show()
        self._btn_install.show()
        self._btn_install.setEnabled(True)

    def _on_no_update(self):
        self._btn_check.setEnabled(True)
        self._set_status(f"✓  You are up to date  (v{__version__})", "#4ADE80")

    def _on_check_failed(self, error: str):
        self._btn_check.setEnabled(True)
        self._set_status(f"✗  Check failed: {error}", "#F87171")

    def _on_progress(self, pct: int):
        self._progress.setValue(pct)

    def _on_download_complete(self):
        self._progress.setValue(100)
        self._set_status("✓  Download complete — ready to restart.", "#4ADE80")

    def _on_update_failed(self, error: str):
        self._btn_check.setEnabled(True)
        self._btn_install.setEnabled(True)
        self._progress.hide()
        self._set_status(f"✗  Update failed: {error}", "#F87171")

    def _on_restart_required(self):
        self._set_status("✓  Update installed — click Restart to apply.", "#4ADE80")
        self._progress.hide()
        self._btn_restart.show()

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _set_status(self, text: str, color: str):
        self._status.setText(text)
        self._status.setStyleSheet(f"color: {color}; font-size: 13px;")
