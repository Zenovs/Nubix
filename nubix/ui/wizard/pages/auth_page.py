"""Wizard authentication page — OAuth2, WebDAV, S3, SFTP, Simple."""

from __future__ import annotations

import subprocess

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QWizardPage,
)

from nubix.providers.base_provider import AuthType


class _RcloneAuthThread(QThread):
    """Runs `rclone authorize --auth-no-open-browser <type>` in a background thread.

    Emits `auth_url` once the browser URL is ready, then `auth_done` once the
    token JSON arrives (after the user completes authorization in the browser).
    """

    auth_url = Signal(str)
    auth_done = Signal(str)
    auth_error = Signal(str)

    def __init__(self, provider_type: str, parent=None):
        super().__init__(parent)
        self._type = provider_type

    def run(self):
        try:
            proc = subprocess.Popen(
                ["rclone", "authorize", self._type, "--auth-no-open-browser"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            url_emitted = False
            token_lines: list[str] = []
            capture = False

            for line in proc.stdout:
                line = line.rstrip()

                # rclone prints the auth URL — extract it regardless of surrounding text
                if not url_emitted and "http" in line:
                    import re

                    match = re.search(r"https?://\S+", line)
                    if match:
                        url = match.group(0).rstrip(".")
                        # skip localhost-only lines (rclone's redirect server)
                        if "accounts." in url or "auth" in url or "oauth" in url or "login" in url:
                            self.auth_url.emit(url)
                            url_emitted = True
                        elif not url_emitted and "127.0.0.1" not in url and "localhost" not in url:
                            self.auth_url.emit(url)
                            url_emitted = True

                # Token appears between ---> and <--- markers
                if "--->" in line:
                    capture = True
                    continue
                if capture and "<---" in line:
                    capture = False
                    continue
                if capture and line.strip().startswith("{"):
                    token_lines.append(line.strip())

            proc.wait()
            if token_lines:
                self.auth_done.emit(token_lines[0])
            elif proc.returncode == 0:
                self.auth_done.emit("")
            else:
                self.auth_error.emit("Authorization failed or was cancelled.")
        except FileNotFoundError:
            self.auth_error.emit("rclone not found. Install it with:  sudo apt install rclone")
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
        self._layout.setSpacing(12)

        self._oauth_widget = self._make_oauth_widget()
        self._layout.addWidget(self._oauth_widget)

        self._webdav_widget = self._make_webdav_widget()
        self._webdav_widget.hide()
        self._layout.addWidget(self._webdav_widget)

        self._s3_widget = self._make_s3_widget()
        self._s3_widget.hide()
        self._layout.addWidget(self._s3_widget)

        self._sftp_widget = self._make_sftp_widget()
        self._sftp_widget.hide()
        self._layout.addWidget(self._sftp_widget)

        self._simple_widget = self._make_simple_widget()
        self._simple_widget.hide()
        self._layout.addWidget(self._simple_widget)

        self._layout.addStretch()

    # ── Widget builders ────────────────────────────────────────────────────────

    def _make_oauth_widget(self) -> QWidget:
        w = QWidget()
        vl = QVBoxLayout(w)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(10)

        self._oauth_info = QLabel(
            "Click the button below. Your browser will open for authorization."
        )
        self._oauth_info.setWordWrap(True)
        vl.addWidget(self._oauth_info)

        self._url_label = QLabel("")
        self._url_label.setWordWrap(True)
        self._url_label.setOpenExternalLinks(True)
        self._url_label.setStyleSheet("color: #7C5CFC; font-size: 12px;")
        self._url_label.hide()
        vl.addWidget(self._url_label)

        self._btn_auth = QPushButton("🌐   Open Browser & Authorize")
        self._btn_auth.setFixedWidth(240)
        self._btn_auth.clicked.connect(self._start_oauth)
        vl.addWidget(self._btn_auth)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("font-size: 12px;")
        vl.addWidget(self._status_label)
        return w

    def _make_webdav_widget(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)

        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText("https://nextcloud.example.com")
        form.addRow("Server URL:", self._url_edit)

        self._webdav_user_edit = QLineEdit()
        self._webdav_user_edit.setPlaceholderText("username")
        form.addRow("Username:", self._webdav_user_edit)

        self._webdav_pass_edit = QLineEdit()
        self._webdav_pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Password:", self._webdav_pass_edit)

        for w_ in (self._url_edit, self._webdav_user_edit, self._webdav_pass_edit):
            w_.textChanged.connect(self.completeChanged)
        return w

    def _make_s3_widget(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)

        self._s3_key = QLineEdit()
        self._s3_key.setPlaceholderText("AKIAIOSFODNN7EXAMPLE")
        form.addRow("Access Key ID:", self._s3_key)

        self._s3_secret = QLineEdit()
        self._s3_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self._s3_secret.setPlaceholderText("wJalrXUtnFEMI/K7MDENG/…")
        form.addRow("Secret Access Key:", self._s3_secret)

        self._s3_region = QLineEdit()
        self._s3_region.setPlaceholderText("us-east-1  (optional)")
        form.addRow("Region:", self._s3_region)

        self._s3_endpoint = QLineEdit()
        self._s3_endpoint.setPlaceholderText("s3.amazonaws.com  (optional, for S3-compatible)")
        form.addRow("Endpoint:", self._s3_endpoint)

        for w_ in (self._s3_key, self._s3_secret):
            w_.textChanged.connect(self.completeChanged)
        return w

    def _make_sftp_widget(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)

        self._sftp_host = QLineEdit()
        self._sftp_host.setPlaceholderText("192.168.1.1  or  my.server.com")
        form.addRow("Host:", self._sftp_host)

        self._sftp_user = QLineEdit()
        self._sftp_user.setPlaceholderText("username")
        form.addRow("Username:", self._sftp_user)

        self._sftp_pass = QLineEdit()
        self._sftp_pass.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Password:", self._sftp_pass)

        for w_ in (self._sftp_host, self._sftp_user):
            w_.textChanged.connect(self.completeChanged)
        return w

    def _make_simple_widget(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)

        self._simple_user = QLineEdit()
        self._simple_user.setPlaceholderText("Email or username")
        form.addRow("Username / Email:", self._simple_user)

        self._simple_pass = QLineEdit()
        self._simple_pass.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Password:", self._simple_pass)

        for w_ in (self._simple_user, self._simple_pass):
            w_.textChanged.connect(self.completeChanged)
        return w

    # ── Page lifecycle ─────────────────────────────────────────────────────────

    def initializePage(self):
        from nubix.providers import get_provider

        provider_id = self.wizard().field("provider_id")
        try:
            provider = get_provider(provider_id)
        except Exception:
            return

        self.setSubTitle(f"Sign in to {provider.display_name}")
        self._token = ""

        # Hide all, show relevant
        for w in (
            self._oauth_widget,
            self._webdav_widget,
            self._s3_widget,
            self._sftp_widget,
            self._simple_widget,
        ):
            w.hide()

        if provider.auth_type == AuthType.WEBDAV_BASIC:
            self._webdav_widget.show()
        elif provider.auth_type == AuthType.S3:
            self._s3_widget.show()
        elif provider.auth_type == AuthType.SFTP:
            self._sftp_widget.show()
        elif provider.auth_type == AuthType.SIMPLE:
            self._simple_widget.show()
        else:  # OAUTH2
            self._oauth_info.setText(
                f"Click the button below. Your browser will open to authorize "
                f"Nubix to access your {provider.display_name}."
            )
            self._status_label.setText("")
            self._url_label.hide()
            self._btn_auth.setEnabled(True)
            self._oauth_widget.show()

    # ── OAuth flow ─────────────────────────────────────────────────────────────

    def _start_oauth(self):
        from nubix.providers import get_provider

        provider_id = self.wizard().field("provider_id")
        try:
            provider = get_provider(provider_id)
        except Exception:
            return

        self._btn_auth.setEnabled(False)
        self._status_label.setText("Starting authorization…")
        self._status_label.setStyleSheet("color: #8888AA; font-size: 12px;")
        self._url_label.hide()

        self._auth_thread = _RcloneAuthThread(provider.get_rclone_type(), self)
        self._auth_thread.auth_url.connect(self._on_auth_url)
        self._auth_thread.auth_done.connect(self._on_auth_done)
        self._auth_thread.auth_error.connect(self._on_auth_error)
        self._auth_thread.start()

    def _on_auth_url(self, url: str):
        # Open the browser with Qt (works in AppImage + Wayland/X11)
        QDesktopServices.openUrl(QUrl(url))
        self._status_label.setText("Browser opened — waiting for authorization…")
        self._status_label.setStyleSheet("color: #60A5FA; font-size: 12px;")
        # Show the URL as fallback link in case browser didn't open
        self._url_label.setText(
            f'If the browser did not open, <a href="{url}" style="color:#7C5CFC;">click here</a>'
            f" or copy this URL manually."
        )
        self._url_label.show()

    def _on_auth_done(self, token: str):
        self._token = token
        self._status_label.setText("✓  Authorization successful!")
        self._status_label.setStyleSheet("color: #4ADE80; font-weight: 600; font-size: 12px;")
        self._url_label.hide()
        self._btn_auth.setEnabled(True)
        self.completeChanged.emit()

    def _on_auth_error(self, error: str):
        self._status_label.setText(f"✗  {error}")
        self._status_label.setStyleSheet("color: #F87171; font-size: 12px;")
        self._btn_auth.setEnabled(True)

    # ── Completion check ───────────────────────────────────────────────────────

    def isComplete(self) -> bool:
        from nubix.providers import get_provider

        provider_id = self.wizard().field("provider_id") or ""
        try:
            provider = get_provider(provider_id)
        except Exception:
            return False

        if provider.auth_type == AuthType.WEBDAV_BASIC:
            return bool(
                self._url_edit.text().strip()
                and self._webdav_user_edit.text().strip()
                and self._webdav_pass_edit.text().strip()
            )
        elif provider.auth_type == AuthType.S3:
            return bool(self._s3_key.text().strip() and self._s3_secret.text().strip())
        elif provider.auth_type == AuthType.SFTP:
            return bool(self._sftp_host.text().strip() and self._sftp_user.text().strip())
        elif provider.auth_type == AuthType.SIMPLE:
            return bool(self._simple_user.text().strip() and self._simple_pass.text().strip())
        else:
            return bool(self._token)

    def get_credentials(self) -> dict:
        from nubix.providers import get_provider

        provider_id = self.wizard().field("provider_id") or ""
        try:
            provider = get_provider(provider_id)
        except Exception:
            return {}

        if provider.auth_type == AuthType.WEBDAV_BASIC:
            return {
                "url": self._url_edit.text().strip(),
                "username": self._webdav_user_edit.text().strip(),
                "password": self._webdav_pass_edit.text().strip(),
            }
        elif provider.auth_type == AuthType.S3:
            return {
                "access_key": self._s3_key.text().strip(),
                "secret_key": self._s3_secret.text().strip(),
                "region": self._s3_region.text().strip(),
                "endpoint": self._s3_endpoint.text().strip(),
            }
        elif provider.auth_type == AuthType.SFTP:
            return {
                "host": self._sftp_host.text().strip(),
                "username": self._sftp_user.text().strip(),
                "password": self._sftp_pass.text().strip(),
            }
        elif provider.auth_type == AuthType.SIMPLE:
            return {
                "username": self._simple_user.text().strip(),
                "password": self._simple_pass.text().strip(),
            }
        return {"token": self._token}
