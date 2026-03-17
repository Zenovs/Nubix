"""
Credential vault for secure storage of cloud provider tokens and passwords.

Primary backend: GNOME Keyring via secretstorage (D-Bus).
Fallback backend: AES-GCM encrypted JSON file.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from nubix.constants import KEYRING_SERVICE, VAULT_FILE
from nubix.exceptions import VaultAccessError

logger = logging.getLogger(__name__)


class CredentialVault:
    """Store and retrieve credentials securely."""

    def __init__(self):
        self._backend = self._init_backend()

    def store(self, remote_id: str, key: str, value: str) -> None:
        """Store a credential."""
        try:
            self._backend.store(remote_id, key, value)
        except Exception as e:
            raise VaultAccessError(str(e)) from e

    def retrieve(self, remote_id: str, key: str) -> str | None:
        """Retrieve a credential. Returns None if not found."""
        try:
            return self._backend.retrieve(remote_id, key)
        except Exception as e:
            raise VaultAccessError(str(e)) from e

    def delete(self, remote_id: str, key: str) -> None:
        """Delete a credential."""
        try:
            self._backend.delete(remote_id, key)
        except Exception as e:
            raise VaultAccessError(str(e)) from e

    def has(self, remote_id: str, key: str) -> bool:
        """Check if a credential exists."""
        try:
            return self._backend.retrieve(remote_id, key) is not None
        except Exception:
            return False

    def delete_all(self, remote_id: str) -> None:
        """Delete all credentials for a remote."""
        try:
            self._backend.delete_all(remote_id)
        except Exception as e:
            logger.warning("Failed to delete all credentials for %s: %s", remote_id, e)

    def _init_backend(self):
        """Try SecretStorage first, fall back to encrypted file."""
        try:
            import secretstorage

            conn = secretstorage.dbus_init()
            collection = secretstorage.get_default_collection(conn)
            if collection.is_locked():
                collection.unlock()
            logger.debug("Using GNOME Keyring backend")
            return _SecretStorageBackend(conn)
        except Exception as e:
            logger.warning("GNOME Keyring unavailable (%s), using encrypted file backend", e)
            return _FileBackend(VAULT_FILE)


class _SecretStorageBackend:
    def __init__(self, connection):
        self._conn = connection

    def _collection(self):
        import secretstorage

        return secretstorage.get_default_collection(self._conn)

    def _attrs(self, remote_id: str, key: str) -> dict:
        return {"service": KEYRING_SERVICE, "remote_id": remote_id, "key": key}

    def store(self, remote_id: str, key: str, value: str) -> None:
        import secretstorage

        col = self._collection()
        label = f"Nubix/{remote_id}/{key}"
        col.create_item(label, self._attrs(remote_id, key), value.encode(), replace=True)

    def retrieve(self, remote_id: str, key: str) -> str | None:
        col = self._collection()
        items = list(col.search_items(self._attrs(remote_id, key)))
        if not items:
            return None
        return items[0].get_secret().decode()

    def delete(self, remote_id: str, key: str) -> None:
        col = self._collection()
        for item in col.search_items(self._attrs(remote_id, key)):
            item.delete()

    def delete_all(self, remote_id: str) -> None:
        col = self._collection()
        attrs = {"service": KEYRING_SERVICE, "remote_id": remote_id}
        for item in col.search_items(attrs):
            item.delete()


class _FileBackend:
    """AES-GCM encrypted JSON file backend."""

    def __init__(self, vault_path: Path):
        self._path = vault_path
        self._key = self._derive_key()
        self._data: dict = self._load()

    def _derive_key(self) -> bytes:
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
        import base64

        # Use machine-id as password (not a secret, but makes the file machine-specific)
        machine_id_file = Path("/etc/machine-id")
        password = (
            machine_id_file.read_bytes()
            if machine_id_file.exists()
            else os.urandom(32)
        )
        salt = b"nubix-vault-v1"
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100_000)
        return base64.urlsafe_b64encode(kdf.derive(password))

    def _load(self) -> dict:
        if not self._path.exists():
            return {}
        try:
            from cryptography.fernet import Fernet

            f = Fernet(self._key)
            encrypted = self._path.read_bytes()
            return json.loads(f.decrypt(encrypted))
        except Exception as e:
            logger.error("Failed to load vault file: %s", e)
            return {}

    def _save(self) -> None:
        from cryptography.fernet import Fernet

        f = Fernet(self._key)
        self._path.write_bytes(f.encrypt(json.dumps(self._data).encode()))

    def store(self, remote_id: str, key: str, value: str) -> None:
        self._data.setdefault(remote_id, {})[key] = value
        self._save()

    def retrieve(self, remote_id: str, key: str) -> str | None:
        return self._data.get(remote_id, {}).get(key)

    def delete(self, remote_id: str, key: str) -> None:
        if remote_id in self._data and key in self._data[remote_id]:
            del self._data[remote_id][key]
            self._save()

    def delete_all(self, remote_id: str) -> None:
        if remote_id in self._data:
            del self._data[remote_id]
            self._save()
