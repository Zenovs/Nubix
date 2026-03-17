"""Shared pytest fixtures."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def tmp_config_dir(tmp_path, monkeypatch):
    """Redirect all config/log directories to a temp path."""
    import nubix.constants as const

    monkeypatch.setattr(const, "CONFIG_DIR", tmp_path / "config")
    monkeypatch.setattr(const, "REMOTES_DIR", tmp_path / "config" / "remotes")
    monkeypatch.setattr(const, "RCLONE_CONFIG_DIR", tmp_path / "config" / "rclone")
    monkeypatch.setattr(const, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(const, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(const, "GLOBAL_CONFIG_FILE", tmp_path / "config" / "config.yaml")
    monkeypatch.setattr(const, "VAULT_FILE", tmp_path / "config" / "vault.enc")
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
