"""Shared pytest fixtures."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest


@pytest.fixture(scope="session", autouse=True)
def qcore_app():
    """Ensure a QCoreApplication exists for the entire test session."""
    from PySide6.QtCore import QCoreApplication

    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication(sys.argv)
    yield app


@pytest.fixture
def tmp_config_dir(tmp_path, monkeypatch):
    """Redirect all config/log directories to a temp path.

    Consuming modules bind these paths at import time via
    `from nubix.constants import …`, so patching nubix.constants alone is
    not enough — the imported names inside each consumer must be patched
    too, or the tests silently read/write the REAL user config.
    """
    import nubix.constants as const
    import nubix.core.config_manager as cm
    import nubix.core.credential_vault as cv

    paths = {
        "CONFIG_DIR": tmp_path / "config",
        "REMOTES_DIR": tmp_path / "config" / "remotes",
        "RCLONE_CONFIG_DIR": tmp_path / "config" / "rclone",
        "LOG_DIR": tmp_path / "logs",
        "CACHE_DIR": tmp_path / "cache",
        "GLOBAL_CONFIG_FILE": tmp_path / "config" / "config.yaml",
        "VAULT_FILE": tmp_path / "config" / "vault.enc",
    }
    for module in (const, cm, cv):
        for name, value in paths.items():
            if hasattr(module, name):
                monkeypatch.setattr(module, name, value)
    return tmp_path


@pytest.fixture
def mock_vault():
    """In-memory credential vault that bypasses D-Bus."""
    vault = MagicMock()
    vault._data: dict = {}

    def store(remote_id, key, value):
        vault._data.setdefault(remote_id, {})[key] = value

    def retrieve(remote_id, key):
        return vault._data.get(remote_id, {}).get(key)

    def has(remote_id, key):
        return retrieve(remote_id, key) is not None

    def delete(remote_id, key):
        if remote_id in vault._data:
            vault._data[remote_id].pop(key, None)

    def delete_all(remote_id):
        vault._data.pop(remote_id, None)

    vault.store.side_effect = store
    vault.retrieve.side_effect = retrieve
    vault.has.side_effect = has
    vault.delete.side_effect = delete
    vault.delete_all.side_effect = delete_all
    return vault
