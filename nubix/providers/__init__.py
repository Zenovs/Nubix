"""Provider registry — covers every rclone backend."""

from __future__ import annotations

from nubix.providers.base_provider import AuthType, BaseProvider


class GenericProvider(BaseProvider):
    """One class handles all rclone provider types dynamically."""

    def __init__(self, provider_id: str, display_name: str, icon: str, auth_type: AuthType):
        self.provider_id = provider_id
        self.display_name = display_name
        self.icon = icon
        self.auth_type = auth_type

    def get_rclone_type(self) -> str:
        # WebDAV-based providers all use the "webdav" rclone backend
        if self.auth_type == AuthType.WEBDAV_BASIC:
            return "webdav"
        return self.provider_id

    def get_rclone_config_args(self, credentials: dict) -> list[str]:
        # First element MUST be the rclone backend type
        args = [self.get_rclone_type()]
        if self.auth_type == AuthType.WEBDAV_BASIC:
            url = credentials.get("url", "").rstrip("/")
            username = credentials.get("username", "")
            # Nextcloud and ownCloud require the full WebDAV URL including the
            # user's files namespace — rclone does not auto-append this path.
            if self.provider_id in ("nextcloud", "owncloud"):
                url = f"{url}/remote.php/dav/files/{username}"
            args += ["url", url]
            # vendor: use provider_id for known vendors, "other" for generic webdav
            vendor = self.provider_id if self.provider_id != "webdav" else "other"
            args += ["vendor", vendor]
            args += ["user", username]
            args += ["pass", credentials.get("password", "")]
        elif self.auth_type == AuthType.S3:
            if self.provider_id in ("azureblob", "azurefiles"):
                # Azure backends take account/key, not S3-style credentials.
                args += ["account", credentials.get("access_key", "")]
                args += ["key", credentials.get("secret_key", "")]
            else:
                args += ["provider", credentials.get("provider", "AWS")]
                args += ["access_key_id", credentials.get("access_key", "")]
                args += ["secret_access_key", credentials.get("secret_key", "")]
                if credentials.get("region"):
                    args += ["region", credentials["region"]]
                if credentials.get("endpoint"):
                    args += ["endpoint", credentials["endpoint"]]
        elif self.auth_type == AuthType.SFTP:
            args += ["host", credentials.get("host", "")]
            args += ["user", credentials.get("username", "")]
            if credentials.get("password"):
                args += ["pass", credentials["password"]]
            else:
                # No password: use SSH key / agent auth. ask_password=false
                # prevents rclone from hanging on a prompt in --non-interactive mode.
                args += ["ask_password", "false"]
        elif self.auth_type == AuthType.SIMPLE:
            args += ["user", credentials.get("username", "")]
            args += ["pass", credentials.get("password", "")]
        elif self.auth_type == AuthType.NONE:
            pass  # local/memory need no credentials — just the backend type
        elif self.auth_type == AuthType.OAUTH2:
            # Google Drive requires scope to be set explicitly so rclone gets
            # full read/write access instead of prompting interactively.
            if self.provider_id == "drive":
                args += ["scope", "drive"]
            if credentials.get("token"):
                args += ["token", credentials["token"]]
        return args


# ── All supported providers ────────────────────────────────────────────────────
# (provider_id, display_name, icon, auth_type)
_ALL: list[tuple[str, str, str, AuthType]] = [
    # ── Google ──
    ("drive", "Google Drive", "🟡", AuthType.OAUTH2),
    ("googlephotos", "Google Photos", "🖼", AuthType.OAUTH2),
    ("gcs", "Google Cloud Storage", "🔷", AuthType.OAUTH2),
    # ── Microsoft ──
    ("onedrive", "Microsoft OneDrive", "🔵", AuthType.OAUTH2),
    ("azureblob", "Azure Blob Storage", "⬡", AuthType.S3),
    ("azurefiles", "Azure Files", "📁", AuthType.S3),
    # ── Dropbox / Box ──
    ("dropbox", "Dropbox", "📦", AuthType.OAUTH2),
    ("box", "Box", "🟦", AuthType.OAUTH2),
    # ── pCloud / HiDrive / Koofr ──
    ("pcloud", "pCloud", "💜", AuthType.OAUTH2),
    ("hidrive", "HiDrive (Strato)", "🟠", AuthType.OAUTH2),
    ("koofr", "Koofr / Internxt", "🟢", AuthType.WEBDAV_BASIC),
    # ── Nextcloud / WebDAV ──
    ("nextcloud", "Nextcloud", "☁", AuthType.WEBDAV_BASIC),
    ("owncloud", "ownCloud", "☁", AuthType.WEBDAV_BASIC),
    ("webdav", "WebDAV (generic)", "🌐", AuthType.WEBDAV_BASIC),
    # ── S3-compatible ──
    ("s3", "Amazon S3", "🟠", AuthType.S3),
    ("b2", "Backblaze B2", "🔵", AuthType.S3),
    ("storj", "Storj DCS", "💠", AuthType.S3),
    ("wasabi", "Wasabi", "🟢", AuthType.S3),
    ("minio", "MinIO (S3)", "🔴", AuthType.S3),
    # ── Scandinavian / European ──
    ("jottacloud", "Jottacloud", "🇳🇴", AuthType.OAUTH2),
    ("yandex", "Yandex Disk", "🔴", AuthType.OAUTH2),
    ("mailru", "Mail.ru Cloud", "📧", AuthType.SIMPLE),
    ("zoho", "Zoho WorkDrive", "🔵", AuthType.OAUTH2),
    # ── Other cloud ──
    ("mega", "MEGA", "🔴", AuthType.SIMPLE),
    ("putio", "Put.io", "⚫", AuthType.OAUTH2),
    ("premiumizeme", "Premiumize.me", "🟤", AuthType.OAUTH2),
    ("fichier", "1Fichier", "📄", AuthType.SIMPLE),
    # ── Network protocols ──
    ("sftp", "SFTP / SSH", "🔑", AuthType.SFTP),
    ("ftp", "FTP", "📡", AuthType.SFTP),
    ("smb", "SMB / Windows Share", "💾", AuthType.SFTP),
    # ── Local / Testing ──
    ("local", "Local Disk / External Drive", "💻", AuthType.NONE),
    ("memory", "In-Memory (testing)", "🧠", AuthType.NONE),
]

# Intentionally NOT offered (they cannot work with this wizard):
#   swift        — needs an auth endpoint + tenant form, has no OAuth flow
#   iclouddrive  — requires interactive 2FA that --non-interactive can't do
#   nfs          — not an rclone backend
#   pixeldrain/linkbox/quatrix — use API keys/tokens, not OAuth
#   crypt/compress/chunker/union — wrap another remote, which the wizard
#                                  has no way to select

PROVIDER_REGISTRY: dict[str, GenericProvider] = {
    pid: GenericProvider(pid, name, icon, auth) for pid, name, icon, auth in _ALL
}


def get_provider(provider_id: str) -> GenericProvider:
    p = PROVIDER_REGISTRY.get(provider_id)
    if not p:
        raise ValueError(f"Unknown provider: {provider_id}")
    return p


def list_providers() -> list[GenericProvider]:
    return list(PROVIDER_REGISTRY.values())
