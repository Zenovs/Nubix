from nubix.providers.google_drive import GoogleDriveProvider
from nubix.providers.dropbox import DropboxProvider
from nubix.providers.nextcloud import NextcloudProvider
from nubix.providers.base_provider import BaseProvider, AuthType

PROVIDER_REGISTRY: dict[str, type[BaseProvider]] = {
    "gdrive": GoogleDriveProvider,
    "dropbox": DropboxProvider,
    "nextcloud": NextcloudProvider,
}


def get_provider(provider_id: str) -> BaseProvider:
    cls = PROVIDER_REGISTRY.get(provider_id)
    if not cls:
        raise ValueError(f"Unknown provider: {provider_id}")
    return cls()
