"""Abstract base class for cloud providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional


class AuthType(str, Enum):
    OAUTH2 = "oauth2"
    WEBDAV_BASIC = "webdav_basic"


class BaseProvider(ABC):
    """Interface every cloud provider must implement."""

    provider_id: str = ""
    display_name: str = ""
    auth_type: AuthType = AuthType.OAUTH2
    icon_name: str = ""  # filename under resources/icons/

    @abstractmethod
    def get_rclone_type(self) -> str:
        """Return the rclone remote type string, e.g. 'drive', 'dropbox'."""
        ...

    @abstractmethod
    def get_rclone_config_args(self, credentials: dict) -> list[str]:
        """
        Return rclone config create arguments for this provider.
        credentials: dict of key-value pairs from the wizard/vault.
        """
        ...

    def get_oauth_url(self) -> str:
        """Return the authorization URL for OAuth2 providers."""
        return ""

    def parse_oauth_callback(self, url: str) -> dict:
        """Extract credentials from the OAuth2 redirect URL."""
        return {}

    def validate_credentials(self, credentials: dict) -> bool:
        """Return True if the credentials look valid (basic check, not network)."""
        return True

    def get_default_remote_path(self) -> str:
        """Default remote root path."""
        return ""
