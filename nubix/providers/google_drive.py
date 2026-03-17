"""Google Drive provider."""

from __future__ import annotations

from nubix.providers.base_provider import AuthType, BaseProvider


class GoogleDriveProvider(BaseProvider):
    provider_id = "gdrive"
    display_name = "Google Drive"
    auth_type = AuthType.OAUTH2
    icon_name = "google_drive.svg"

    def get_rclone_type(self) -> str:
        return "drive"

    def get_rclone_config_args(self, credentials: dict) -> list[str]:
        args = [self.get_rclone_type()]
        # If user provides custom OAuth app credentials
        if credentials.get("client_id"):
            args += ["client_id", credentials["client_id"]]
        if credentials.get("client_secret"):
            args += ["client_secret", credentials["client_secret"]]
        if credentials.get("token"):
            args += ["token", credentials["token"]]
        # scope: drive = full access, drive.file = app-created files only
        scope = credentials.get("scope", "drive")
        args += ["scope", scope]
        return args

    def get_oauth_url(self) -> str:
        # rclone handles the full OAuth flow via `rclone authorize drive`
        # We return empty string — the engine uses rclone's authorize command
        return ""

    def get_default_remote_path(self) -> str:
        return ""
