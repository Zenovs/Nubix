"""Wizard authentication page — handles OAuth2 and WebDAV."""

from __future__ import annotations

import subprocess
import threading

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWizardPage,
)

from nubix.providers import get_provider
from nubix.providers.base_provider import AuthType


class _RcloneAuthThread(QThread):
    """Runs `rclone authorize <type>` in a background thread."""

    auth_done = Signal(str)  # token JSON string
    auth_error = Signal(str)

    def __init__(self, provider_type: str, parent=None):
        super().__init__(parent)
        self._type = provider_type

    def run(self):
        try:
            result = subprocess.run(
                ["rclone", "authorize", self._type],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode == 0:
                # Token appears on stdout
                token_line = result.stdout.strip().splitlines()[-1] if result.stdout else ""
                self.auth_done.emit(token_line)
            else:
                self.auth_error.emit(result.stderr or "Authorization failed")
        except Exception as e:
            self.auth_error.emit(str(e))


class AuthPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Connect Your Account")
        self._auth_thread: _RcloneAuthThread | None = None
        self._token: str = ""
        self._build_ui()

    def _build_ui(self):
        self._layout = QVBoxLayout(self)

        # OAuth section
        self._oauth_widget = self._make_oauth_widget()
        self._layout.addWidget(self._oauth_widget)

        # WebDAV section (hidden by default)
        self._webdav_widget = self._make_webdav_widget()
        self._webdav_widget.hide()
        self._layout.addWidget(self._webdav_widget)

        self._layout.addStretch()

    def _make_oauth_widget(self):
        from PySide6.QtWidgets import QWidget

        w = QWidget()
        vl = QVBoxLayout(w)
        self._oauth_info = QLabel(
            "Click the button below to open your browser and authorize Nubix."
        )
        self._oauth_info.setWordWrap(True)
        vl.addWidget(self._oauth_info)

        self._btn_auth = QPushButton("Open Browser & Authorize")
        self._btn_auth.setFixedWidth(220)
        self._btn_auth.clicked.connect(self._start_oauth)
        vl.addWidget(self._btn_auth)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #555; font-size: 12px;")
        vl.addWidget(self._status_label)
        return w

    def _make_webdav_widget(self):
        from PySide6.QtWidgets import QWidget

        w = QWidget()
        form = QFormLayout(w)

        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText("https://nextcloud.example.com")
        form.addRow("Server URL:", self._url_edit)

        self._user_edit = QLineEdit()
        self._user_edit.setPlaceholderText("username")
        form.addRow("Username:", self._user_edit)

        self._pass_edit = QLineEdit()
        self._pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Password:", self._pass_edit)

        # Connect to completeChanged
        self._url_edit.textChanged.connect(self.completeChanged)
        self._user_edit.textChanged.connect(self.completeChanged)
        self._pass_edit.textChanged.connect(self.completeChanged)

        return w

    def initializePage(self):
        provider_id = self.wizard().field("provider_id")
        try:
            provider = get_provider(provider_id)
        except Exception:
            return

        self.setSubTitle(f"Sign in to {provider.display_name}")

        if provider.auth_type == AuthType.WEBDAV_BASIC:
            self._oauth_widget.hide()
            self._webdav_widget.show()
        else:
            self._webdav_widget.hide()
            self._oauth_widget.show()
            self._oauth_info.setText(
                f"Click the button below to open your browser and "
                f"authorize Nubix to access your {provider.display_name}."
            )

    def _start_oauth(self):
        provider_id = self.wizard().field("provider_id")
        try:
            provider = get_provider(provider_id)
        except Exception:
            return

        self._btn_auth.setEnabled(False)
        self._status_label.setText("Waiting for authorization in browser…")
        self._auth_thread = _RcloneAuthThread(provider.get_rclone_type())
        self._auth_thread.auth_done.connect(self._on_auth_done)
        self._auth_thread.auth_error.connect(self._on_auth_error)
        self._auth_thread.start()

    def _on_auth_done(self, token: str):
        self._token = token
        self._status_label.setText("✓ Authorization successful!")
        self._status_label.setStyleSheet("color: #388E3C; font-weight: bold;")
        self._btn_auth.setEnabled(True)
        self.completeChanged.emit()

    def _on_auth_error(self, error: str):
        self._status_label.setText(f"✗ Failed: {error}")
        self._status_label.setStyleSheet("color: #D32F2F;")
        self._btn_auth.setEnabled(True)

    def isComplete(self) -> bool:
        provider_id = self.wizard().field("provider_id") or ""
        try:
            provider = get_provider(provider_id)
        except Exception:
            return False

        if provider.auth_type == AuthType.WEBDAV_BASIC:
            return all(
                [
                    self._url_edit.text().strip(),
                    self._user_edit.text().strip(),
                    self._pass_edit.text().strip(),
                ]
            )
        else:
            return bool(self._token)

    def get_credentials(self) -> dict:
        provider_id = self.wizard().field("provider_id") or ""
        try:
            provider = get_provider(provider_id)
        except Exception:
            return {}

        if provider.auth_type == AuthType.WEBDAV_BASIC:
            return {
                "url": self._url_edit.text().strip(),
                "username": self._user_edit.text().strip(),
                "password": self._pass_edit.text().strip(),
            }
        return {"token": self._token}
