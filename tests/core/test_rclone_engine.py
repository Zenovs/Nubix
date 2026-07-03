"""Tests for RcloneEngine.configure_remote (direct config-file writing)."""

from unittest.mock import patch

import pytest

import nubix.core.rclone_engine as eng_mod
from nubix.core.rclone_engine import RcloneEngine


@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.setattr(eng_mod, "RCLONE_CONFIG_FILE", tmp_path / "rclone.conf")
    e = RcloneEngine.__new__(RcloneEngine)
    e._binary = "/bin/true"
    e._resync_ack = None
    return e


def test_configure_remote_writes_section(engine, tmp_path):
    ok = engine.configure_remote("gd_abc", ["drive", "scope", "drive", "token", '{"x": 1}'])
    assert ok
    text = (tmp_path / "rclone.conf").read_text()
    assert "[gd_abc]" in text
    assert "type = drive" in text
    assert "scope = drive" in text


def test_configure_remote_obscures_password(engine, tmp_path):
    with patch.object(RcloneEngine, "_obscure", return_value="OBSCURED") as obscure:
        ok = engine.configure_remote(
            "nc_1", ["webdav", "url", "https://x", "user", "u", "pass", "secret"]
        )
    assert ok
    obscure.assert_called_once_with("secret")
    text = (tmp_path / "rclone.conf").read_text()
    assert "secret" not in text
    assert "pass = OBSCURED" in text


def test_configure_remote_preserves_existing_sections(engine, tmp_path):
    assert engine.configure_remote("first", ["s3", "provider", "AWS"])
    assert engine.configure_remote("second", ["local"])
    text = (tmp_path / "rclone.conf").read_text()
    assert "[first]" in text and "[second]" in text


def test_configure_remote_rejects_malformed_args(engine):
    assert not engine.configure_remote("bad", ["drive", "orphan-key"])
    assert not engine.configure_remote("empty", [])


def test_configure_remote_sets_restrictive_permissions(engine, tmp_path):
    engine.configure_remote("r", ["local"])
    mode = (tmp_path / "rclone.conf").stat().st_mode & 0o777
    assert mode == 0o600


def test_configure_remote_fails_when_obscure_fails(engine, tmp_path):
    with patch.object(RcloneEngine, "_obscure", return_value=None):
        ok = engine.configure_remote("nc_1", ["webdav", "pass", "secret"])
    assert not ok
