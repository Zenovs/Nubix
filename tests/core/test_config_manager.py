"""Tests for ConfigManager."""

from __future__ import annotations

import pytest

from nubix.core.config_manager import ConfigManager


def test_default_values_are_set(tmp_config_dir):
    config = ConfigManager()
    assert config.get("general.autostart") is False
    assert config.get("general.minimize_to_tray") is True


def test_set_and_get_roundtrip(tmp_config_dir):
    config = ConfigManager()
    config.set("general.autostart", True)
    assert config.get("general.autostart") is True


def test_default_returned_for_missing_key(tmp_config_dir):
    config = ConfigManager()
    assert config.get("nonexistent.key", "fallback") == "fallback"


def test_config_persisted_across_instances(tmp_config_dir):
    c1 = ConfigManager()
    c1.set("general.log_retention_days", 99)
    c2 = ConfigManager()
    assert c2.get("general.log_retention_days") == 99


def test_config_changed_signal_emitted(tmp_config_dir):
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication.instance() or QApplication(sys.argv)
    config = ConfigManager()
    received = []
    config.config_changed.connect(lambda k, v: received.append((k, v)))
    config.set("general.autostart", True)
    assert ("general.autostart", True) in received


def test_remote_config_save_and_load(tmp_config_dir):
    config = ConfigManager()
    data = {"remote_id": "test123", "provider_type": "gdrive", "local_path": "/tmp/test"}
    config.save_remote_config("test123", data)
    loaded = config.get_remote_config("test123")
    assert loaded["remote_id"] == "test123"
    assert loaded["provider_type"] == "gdrive"


def test_delete_remote_config(tmp_config_dir):
    config = ConfigManager()
    config.save_remote_config("to_delete", {"foo": "bar"})
    config.delete_remote_config("to_delete")
    assert config.get_remote_config("to_delete") is None


def test_list_remote_ids(tmp_config_dir):
    config = ConfigManager()
    config.save_remote_config("remote_a", {"x": 1})
    config.save_remote_config("remote_b", {"x": 2})
    ids = config.list_remote_ids()
    assert "remote_a" in ids
    assert "remote_b" in ids
