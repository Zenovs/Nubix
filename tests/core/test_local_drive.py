"""Tests for local drive availability detection (external drive sync paths)."""

from pathlib import Path

import pytest

from nubix.core.local_drive import is_drive_available, missing_mount_for


@pytest.fixture
def mounts(monkeypatch):
    """Control which paths report as active mount points."""
    mounted: set[str] = set()
    monkeypatch.setattr("os.path.ismount", lambda p: str(p) in mounted)
    return mounted


def test_home_path_is_always_available(mounts):
    assert missing_mount_for(Path("/home/user/Nextcloud")) is None
    assert is_drive_available(Path("/home/user/Nextcloud"))


def test_run_media_unmounted_reports_mount_point(mounts):
    path = Path("/run/media/dario/6TB-HDD/nubix/dropbox")
    assert missing_mount_for(path) == Path("/run/media/dario/6TB-HDD")
    assert not is_drive_available(path)


def test_run_media_mounted_is_available(mounts):
    mounts.add("/run/media/dario/6TB-HDD")
    path = Path("/run/media/dario/6TB-HDD/nubix/dropbox")
    assert missing_mount_for(path) is None


def test_media_unmounted_reports_mount_point(mounts):
    assert missing_mount_for(Path("/media/backup/docs")) == Path("/media/backup")


def test_media_mounted_deeper_level_is_available(mounts):
    # Debian-style /media/<user>/<label> layout
    mounts.add("/media/dario/USB-Stick")
    assert missing_mount_for(Path("/media/dario/USB-Stick/sync")) is None


def test_mnt_fstab_mount_available(mounts):
    mounts.add("/mnt/hdd")
    assert missing_mount_for(Path("/mnt/hdd/github/data")) is None


def test_mnt_unmounted_is_blocked(mounts):
    assert missing_mount_for(Path("/mnt/hdd/github/data")) == Path("/mnt/hdd")


def test_path_that_is_itself_the_mount_point(mounts):
    mounts.add("/run/media/dario/6TB-HDD")
    assert missing_mount_for(Path("/run/media/dario/6TB-HDD")) is None


def test_removable_root_itself_is_not_checked(mounts):
    # /mnt itself is not "under" a removable root — no mount requirement
    assert missing_mount_for(Path("/mnt")) is None


def test_tilde_is_expanded(mounts):
    assert missing_mount_for(Path("~/Documents/sync")) is None
