"""Wizard authentication page — OAuth2, WebDAV, S3, SFTP, Simple."""

from __future__ import annotations

import os
import shutil
import subprocess

from PySide6.QtCore import QThread, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QWizardPage,
)

from nubix.providers.base_provider import AuthType


def _open_browser(url: str) -> None:
    """Open a URL in the default browser (fallback / manual open button).

    Uses a clean LD_LIBRARY_PATH so xdg-open works inside an AppImage.
    """
    import logging

    _log = logging.getLogger(__name__)

    env = _clean_env()

    # Try xdg-open; wait briefly to detect immediate failure
    xdg = shutil.which("xdg-open")
    if xdg:
        try:
            proc = subprocess.Popen(
                [xdg, url],
                env=env,
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            import time

            time.sleep(0.15)  # give xdg-open a moment to exit with an error
            ret = proc.poll()
            if ret is None or ret == 0:
                return  # still running (spawned browser) or clean exit
            _log.warning("xdg-open exited with code %d, trying fallbacks", ret)
        except Exception as exc:
            _log.warning("xdg-open failed: %s", exc)

    # Try common browsers directly (skips xdg-open entirely)
    for browser in ("firefox", "chromium-browser", "chromium", "google-chrome", "brave-browser"):
        path = shutil.which(browser)
        if path:
            try:
                subprocess.Popen([path, url], env=env, start_new_session=True)
                _log.debug("Opened browser via %s", browser)
                return
            except Exception:
                continue

    # Last resort: Qt (may not work inside AppImage but better than nothing)
    _log.debug("Falling back to QDesktopServices.openUrl")
    QDesktopServices.openUrl(QUrl(url))


def _kill_rclone_authorize() -> None:
    """Kill any lingering 'rclone authorize' processes to free port 53682.

    Handles zombie processes left over from previous wizard sessions or app
    restarts where cleanupPage() was never called.
    """
    import signal

    try:
        result = subprocess.run(
            ["pgrep", "-f", "rclone authorize"],
            capture_output=True,
            text=True,
        )
        for pid_str in result.stdout.split():
            try:
                os.kill(int(pid_str), signal.SIGKILL)
            except ProcessLookupError:
                pass
    except Exception:
        pass


def _clean_env() -> dict:
    """Return os.environ with LD_LIBRARY_PATH restored to pre-AppImage value.

    When Nubix runs as an AppImage the runtime overrides LD_LIBRARY_PATH to
    point to its bundled libs.  Any child process (rclone, xdg-open, browsers)
    that inherits this env will load the wrong glib/gio and silently fail.
    We restore the original value before spawning any subprocess.
    """
    env = os.environ.copy()
    orig = env.get("APPIMAGE_ORIGINAL_LD_LIBRARY_PATH")
    if orig is not None:
        env["LD_LIBRARY_PATH"] = orig
    elif "APPIMAGE" in env:
        env.pop("LD_LIBRARY_PATH", None)
    return env


class _RcloneAuthThread(QThread):
    """Runs `rclone authorize <type>` and emits the auth URL and token.

    rclone opens the browser itself (no --auth-no-open-browser so this works
    with any rclone version, including the older ones shipped by Ubuntu apt).
    We spawn rclone with a clean LD_LIBRARY_PATH so that when rclone calls
    xdg-open internally it uses system libs, not the AppImage-bundled ones.
    We also parse the URL from the output so the UI can show it as a copyable
    fallback in case the browser did not open.
    """

    auth_url = Signal(str)  # emitted as soon as URL is detected in output
    auth_done = Signal(str)  # emitted with token JSON once auth completes
    auth_error = Signal(str)

    def __init__(self, provider_type: str, parent=None):
        super().__init__(parent)
        self._type = provider_type
        self._proc: subprocess.Popen | None = None

    def cancel(self) -> None:
        """Kill the rclone process immediately so it releases port 53682."""
        if self._proc is not None:
            try:
                self._proc.kill()  # SIGKILL — immediate, no grace period
                self._proc.wait()
            except Exception:
                pass
            self._proc = None

    def run(self):
        try:
            # Use --auth-no-open-browser so rclone only starts the local server
            # and outputs the URL; we open the browser ourselves with a clean
            # LD_LIBRARY_PATH (so xdg-open works inside AppImage).
            # This flag is available since rclone v1.59.
            proc = subprocess.Popen(
                ["rclone", "authorize", self._type, "--auth-no-open-browser"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=_clean_env(),
            )
            self._proc = proc
        except FileNotFoundError:
            self.auth_error.emit("rclone not found. Install it with:  sudo apt install rclone")
            return
        except Exception as e:
            self.auth_error.emit(str(e))
            return

        import re

        url_emitted = False
        token_lines: list[str] = []
        all_lines: list[str] = []
        capture = False

        for raw in proc.stdout:
            line = raw.rstrip()
            all_lines.append(line)

            # Extract the authorization URL from rclone output.
            # rclone prints two URL-containing lines:
            #   1) NOTICE: Make sure your Redirect URL is set to "http://127.0.0.1:53682/"
            #   2) NOTICE: go to the following link: http://127.0.0.1:53682/auth?...
            # We want line 2. Prefer the "link: URL" pattern; fall back to any
            # URL that is NOT surrounded by quotes (which is the redirect notice).
            if not url_emitted and "http" in line:
                # Primary: explicit "link: <url>" marker used by rclone
                m = re.search(r"link:\s*(https?://[^\s\"']+)", line, re.IGNORECASE)
                if not m:
                    # Fallback: URL NOT immediately preceded by a quote character
                    m = re.search(r'(?<!["\'`])(https?://[^\s"\'`]+)', line)
                if m:
                    url = m.group(1).rstrip(".,)")
                    self.auth_url.emit(url)
                    url_emitted = True

            # Token arrives between ---> and <--- markers
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
            snippet = "\n".join(all_lines[-20:]).strip() if all_lines else ""
            msg = f"rclone exited with code {proc.returncode}."
            if snippet:
                msg += f"\n\n{snippet}"
            self.auth_error.emit(msg)


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

    # ── OAuth widget ───────────────────────────────────────────────────────────

    def _make_oauth_widget(self) -> QWidget:
        w = QWidget()
        vl = QVBoxLayout(w)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(10)

        self._oauth_info = QLabel(
            "Click the button below — your browser will open for authorization.\n"
            "If the browser does not open automatically, copy the link below."
        )
        self._oauth_info.setWordWrap(True)
        self._oauth_info.setStyleSheet("color: #8888AA; font-size: 12px;")
        vl.addWidget(self._oauth_info)

        # Start button
        self._btn_auth = QPushButton("🌐   Open Browser and Authorize")
        self._btn_auth.setFixedHeight(38)
        self._btn_auth.clicked.connect(self._start_oauth)
        vl.addWidget(self._btn_auth)

        # Status line
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("font-size: 12px; font-weight: 600;")
        self._status_label.setWordWrap(True)
        vl.addWidget(self._status_label)

        # ── Copyable URL box (hidden until URL arrives) ──
        url_header = QLabel("Authorization URL  (copy and open manually if needed):")
        url_header.setStyleSheet("color: #8888AA; font-size: 11px; font-weight: 600;")
        url_header.hide()
        vl.addWidget(url_header)
        self._url_header = url_header

        url_row = QHBoxLayout()
        self._url_field = QLineEdit()
        self._url_field.setReadOnly(True)
        self._url_field.setStyleSheet(
            "QLineEdit { background: #1E1E32; border: 1px solid #7C5CFC;"
            " border-radius: 6px; padding: 6px 10px; color: #A78BFA;"
            " font-size: 11px; }"
        )
        self._url_field.hide()
        url_row.addWidget(self._url_field, 1)

        self._btn_copy = QPushButton("Copy")
        self._btn_copy.setFixedWidth(64)
        self._btn_copy.setStyleSheet(
            "QPushButton { background: #2E2E50; color: #E2E2F0; border: 1px solid #7C5CFC;"
            " border-radius: 6px; padding: 6px; font-size: 12px; }"
            "QPushButton:hover { background: #7C5CFC; color: white; }"
        )
        self._btn_copy.hide()
        self._btn_copy.clicked.connect(self._copy_url)
        url_row.addWidget(self._btn_copy)

        self._btn_open = QPushButton("Open")
        self._btn_open.setFixedWidth(64)
        self._btn_open.setStyleSheet(
            "QPushButton { background: #2E2E50; color: #E2E2F0; border: 1px solid #7C5CFC;"
            " border-radius: 6px; padding: 6px; font-size: 12px; }"
            "QPushButton:hover { background: #7C5CFC; color: white; }"
        )
        self._btn_open.hide()
        self._btn_open.clicked.connect(self._open_url_manually)
        url_row.addWidget(self._btn_open)

        vl.addLayout(url_row)

        return w

    # ── Other auth forms ───────────────────────────────────────────────────────

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

        for field in (self._url_edit, self._webdav_user_edit, self._webdav_pass_edit):
            field.textChanged.connect(self.completeChanged)
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
        self._s3_endpoint.setPlaceholderText("s3.amazonaws.com  (optional)")
        form.addRow("Endpoint:", self._s3_endpoint)

        for field in (self._s3_key, self._s3_secret):
            field.textChanged.connect(self.completeChanged)
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

        for field in (self._sftp_host, self._sftp_user):
            field.textChanged.connect(self.completeChanged)
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

        for field in (self._simple_user, self._simple_pass):
            field.textChanged.connect(self.completeChanged)
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
        self._status_label.setText("")
        self._url_field.clear()
        self._url_field.hide()
        self._url_header.hide()
        self._btn_copy.hide()
        self._btn_open.hide()
        self._btn_auth.setEnabled(True)

        for widget in (
            self._oauth_widget,
            self._webdav_widget,
            self._s3_widget,
            self._sftp_widget,
            self._simple_widget,
        ):
            widget.hide()

        if provider.auth_type == AuthType.WEBDAV_BASIC:
            self._webdav_widget.show()
        elif provider.auth_type == AuthType.S3:
            self._s3_widget.show()
        elif provider.auth_type == AuthType.SFTP:
            self._sftp_widget.show()
        elif provider.auth_type == AuthType.SIMPLE:
            self._simple_widget.show()
        else:
            self._oauth_widget.show()

    # ── OAuth flow ─────────────────────────────────────────────────────────────

    def cleanupPage(self):
        """Called when the user navigates away — kill any running rclone process."""
        if self._auth_thread is not None:
            self._auth_thread.cancel()
            self._auth_thread.quit()
            self._auth_thread.wait(2000)
            self._auth_thread = None

    def _start_oauth(self):
        from nubix.providers import get_provider

        # Kill any previous rclone process so port 53682 is released before
        # we start a new one (otherwise rclone exits immediately with
        # "bind: address already in use" and the browser never opens).
        if self._auth_thread is not None:
            self._auth_thread.cancel()
            self._auth_thread.quit()
            self._auth_thread.wait(2000)
            self._auth_thread = None
        # Also kill any zombie rclone authorize processes from previous
        # sessions (wizard closed without navigating back, app restart, etc.)
        _kill_rclone_authorize()

        provider_id = self.wizard().field("provider_id")
        try:
            provider = get_provider(provider_id)
        except Exception:
            self._set_status("✗  No provider selected — go back and choose one.", "#F87171")
            return

        self._btn_auth.setEnabled(False)
        self._url_field.clear()
        self._url_field.hide()
        self._url_header.hide()
        self._btn_copy.hide()
        self._btn_open.hide()
        self._set_status("⏳  Starting authorization…", "#8888AA")

        self._auth_thread = _RcloneAuthThread(provider.get_rclone_type(), self)
        self._auth_thread.auth_url.connect(self._on_auth_url)
        self._auth_thread.auth_done.connect(self._on_auth_done)
        self._auth_thread.auth_error.connect(self._on_auth_error)
        self._auth_thread.start()

    def _on_auth_url(self, url: str):
        # We use --auth-no-open-browser, so we open the browser ourselves.
        _open_browser(url)
        self._url_field.setText(url)
        self._url_field.show()
        self._url_header.show()
        self._btn_copy.show()
        self._btn_open.show()
        self._set_status(
            "🌐  Browser opened for authorization.\n"
            "If it did not open, copy the URL below and paste it into your browser.",
            "#60A5FA",
        )

    def _on_auth_done(self, token: str):
        self._token = token
        self._set_status("✓  Authorization successful!", "#4ADE80")
        self._url_field.hide()
        self._url_header.hide()
        self._btn_copy.hide()
        self._btn_open.hide()
        self._btn_auth.setEnabled(True)
        self.completeChanged.emit()

    def _on_auth_error(self, error: str):
        self._set_status(f"✗  {error}", "#F87171")
        self._btn_auth.setEnabled(True)

    def _copy_url(self):
        url = self._url_field.text()
        if url:
            QApplication.clipboard().setText(url)
            self._btn_copy.setText("✓")
            from PySide6.QtCore import QTimer

            QTimer.singleShot(2000, lambda: self._btn_copy.setText("Copy"))

    def _open_url_manually(self):
        url = self._url_field.text()
        if url:
            _open_browser(url)

    def _set_status(self, text: str, color: str):
        self._status_label.setText(text)
        self._status_label.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {color};")

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
