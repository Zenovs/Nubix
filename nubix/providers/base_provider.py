"""Abstract base class for cloud providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum


class AuthType(str, Enum):
    OAUTH2 = "oauth2"
    WEBDAV_BASIC = "webdav_basic"
    S3 = "s3"
    SFTP = "sftp"
    SIMPLE = "simple"  # email + password (MEGA, etc.)


class BaseProvider(ABC):
    """Interface every cloud provider must implement."""

    provider_id: str = ""
    display_name: str = ""
    auth_type: AuthType = AuthType.OAUTH2
    icon: str = "☁"

    @abstractmethod
    def get_rclone_type(self) -> str:
        """Return the rclone remote type string, e.g. 'drive', 'dropbox'."""
        ...

    @abstractmethod
    def get_rclone_config_args(self, credentials: dict) -> list[str]:
        """Return rclone config create arguments for this provider."""
        ...

    def validate_credentials(self, credentials: dict) -> bool:
        return True

    def get_default_remote_path(self) -> str:
        return ""
