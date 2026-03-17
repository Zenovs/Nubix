"""Dropbox provider."""

from __future__ import annotations

from nubix.providers.base_provider import AuthType, BaseProvider


class DropboxProvider(BaseProvider):
    provider_id = "dropbox"
    display_name = "Dropbox"
    auth_type = AuthType.OAUTH2
    icon_name = "dropbox.svg"

    def get_rclone_type(self) -> str:
        return "dropbox"

    def get_rclone_config_args(self, credentials: dict) -> list[str]:
        args = [self.get_rclone_type()]
        if credentials.get("client_id"):
            args += ["client_id", credentials["client_id"]]
        if credentials.get("client_secret"):
            args += ["client_secret", credentials["client_secret"]]
        if credentials.get("token"):
            args += ["token", credentials["token"]]
        return args

    def get_default_remote_path(self) -> str:
        return ""
