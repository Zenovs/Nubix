"""Nextcloud (WebDAV) provider."""

from __future__ import annotations

import subprocess

from nubix.providers.base_provider import AuthType, BaseProvider


def _rclone_obscure(password: str) -> str:
    """Use rclone obscure to encode a WebDAV password."""
    try:
        result = subprocess.run(
            ["rclone", "obscure", password],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip()
    except Exception:
        return password


class NextcloudProvider(BaseProvider):
    provider_id = "nextcloud"
    display_name = "Nextcloud"
    auth_type = AuthType.WEBDAV_BASIC
    icon_name = "nextcloud.svg"

    def get_rclone_type(self) -> str:
        return "webdav"

    def get_rclone_config_args(self, credentials: dict) -> list[str]:
        url = (
            credentials.get("url", "").rstrip("/")
            + "/remote.php/dav/files/"
            + credentials.get("username", "")
        )
        password = credentials.get("password", "")
        obscured = _rclone_obscure(password)
        return [
            self.get_rclone_type(),
            "url",
            url,
            "vendor",
            "nextcloud",
            "user",
            credentials.get("username", ""),
            "pass",
            obscured,
        ]

    def validate_credentials(self, credentials: dict) -> bool:
        required = ("url", "username", "password")
        return all(credentials.get(k, "").strip() for k in required)

    def get_default_remote_path(self) -> str:
        return ""
